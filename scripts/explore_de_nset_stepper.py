#!/usr/bin/env python3
"""explore_de_nset_stepper.py — LINE X, Germany data-driven emulator, track D-NSET: the MINIMAL SH6
ENGINE ADAPTER
for the stage-2 gate's free run (pre-registration /p/tmp/jamirp/X_de/_status/D.md, gate part b).

  python explore_de_engine.py run --arm nset_D-main --stepper explore_de_nset_stepper:NsetStepper \
      --kwargs '{"arm": "D-main"}' --gcm MPI-ESM1-2-HR --seed 1 --start 2014 --end 2044 --legs
      ssp370 --cells FILE

One step y -> y+1 for every printed living tree of the state: the set model sees each patch's padded
roster (same
featurisation as training: explore_de_nset_model.token_raw_to_feat), the grass token, the patch LSTM
state (aux_patch)
and the cell climate window y-20 .. y+1 (built with the SH11 climate builder, so training and
rollout read one
definition). Sampling order: G_{y+1} (sign, then magnitude) -> counter by the SH2 rule -> growth
vector -> SH2 rule
hazard (mortality_step with the sampled G and water integral and the year's temperature-stress days)
-> demographic
death with the learned correction, fire with the learned patch fraction -> "drops below 5 m"
(hidden, removed next
step) -> recruit count (NB), Type, 4 traits (copy / background), Longevity + beta_root by the SH2
rules, entry state
-> grass LAI (two-part; agb = 23.673 LAI, cover = 1 - exp(-0.5 LAI) capped at 1 - tree cover) ->
LSTM advance.
Randomness: per-tree uniforms from the engine's counter-based Rand (death, visibility); the rest
from a torch / numpy
generator seeded by (arm, rep, year), so a run is reproducible for a fixed chunking (not
chunk-invariant).
"""

from __future__ import annotations

import hashlib
import os
import sys

import numpy as np
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_engine as eng  # noqa: E402
import explore_de_nset_model as nm  # noqa: E402
import explore_de_nset_train as ntr  # noqa: E402
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_tensors as st  # noqa: E402

PB = 8192  # patches per GPU batch


def _seed(*parts) -> int:
    return int.from_bytes(
        hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big"
    ) % (2**63)


class NsetStepper:
    needs_bank = False

    def __init__(self, arm: str = "D-main", device: str | None = None):
        self.arm = arm
        self.dev = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))

    def init(self, state, ctx):
        self.model = ntr.load_model(self.arm, self.dev)
        self.P = ctx["P"]
        self.cells = state.cell["cells"]
        self.gcm = ctx["gcm"]
        self.rep = ctx["rep"]
        self.stat = st.static_tensor(self.gcm, self.cells)
        self.clim = {}
        self.y0 = 1960
        self.n_clip = {"S_over_40": 0, "fpc_clip": 0, "grass_capped": 0}

    def _climwin(self, traj, year):
        if traj not in self.clim:
            self.clim[traj] = st.climate_tensor(self.gcm, traj, self.cells, self.y0, 2045)
        a = self.clim[traj]
        return a[:, year - 20 - self.y0 : year + 2 - self.y0]

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        m, N, dev = self.model, self.model.norm, self.dev
        t = state.tree
        n = state.n
        npatch = state.npatch
        Ptot = len(self.cells) * npatch
        live = ~t["hidden"] & ~t["isdead"]
        li = np.flatnonzero(live)
        pidx = state.patch_index()
        pl_ = pidx[li]
        order = np.lexsort((t["ID"][li], -t["Height"][li].astype(np.float64), pl_))
        li = li[order]
        pl_ = pidx[li]
        first = np.r_[True, pl_[1:] != pl_[:-1]] if len(li) else np.zeros(0, bool)
        start = np.flatnonzero(first)
        grp = np.cumsum(first) - 1
        slot = np.arange(len(li)) - start[grp] if len(li) else np.zeros(0, np.int64)
        nlive = np.bincount(pl_, minlength=Ptot)
        S = max(int(nlive.max()) if len(li) else 1, 1)
        self.n_clip["S_over_40"] += int(S > 40)
        R = {
            c: t[c][li].astype(np.float64)
            for c in [
                "SLA",
                "Wooddens",
                "D95max",
                "minwscal",
                "Longevity",
                "beta_root",
                "Height",
                "agb",
                "vegc",
                "LAI",
                "fpc_ind",
                "D95",
                "Age",
                "npp",
                "transp",
                "wscal_mean",
            ]
        }
        R["Type"] = t["Type"][li]
        R["c_y"] = t["c"][li].astype(np.float64)
        R["G_y"] = np.nan_to_num(t["G"][li].astype(np.float64))
        R["W_y"] = np.nan_to_num(t["W"][li].astype(np.float64))
        R["height_rank"] = slot + 1.0
        R["is_reentry_y"] = np.zeros(len(li))
        R["n_live"] = nlive[pl_].astype(np.float64)
        TF, typ = nm.token_raw_to_feat(R)
        # padded
        tokf = np.zeros((Ptot, S, TF.shape[1]), np.float32)
        tokf[pl_, slot] = TF
        ptyp = np.zeros((Ptot, S), np.int64)
        ptyp[pl_, slot] = typ
        pc_ = np.zeros((Ptot, S), np.int64)
        pc_[pl_, slot] = np.clip(t["c"][li], 0, nm.NC)
        pmask = np.zeros((Ptot, S), bool)
        pmask[pl_, slot] = True
        X4 = np.zeros((Ptot, S, 4), np.float32)
        X4[pl_, slot] = nm.trait4(R)
        sum_fpc = np.bincount(pl_, weights=R["fpc_ind"], minlength=Ptot)
        sum_agb = np.bincount(pl_, weights=R["agb"], minlength=Ptot)
        gp = state.patch
        GF = nm.grass_feat(gp["grass8_fpc"], gp["grass8_LAI"], gp["grass8_agb"])
        PS = nm.patch_scal(nlive, sum_fpc, sum_agb, None if m.lstm_on else gp["loss_ring"])
        cw = self._climwin(ctx["traj"], year)  # [C, 22, Fc]
        ci_p = np.repeat(np.arange(len(self.cells)), npatch)
        gen = torch.Generator(device=dev)
        gen.manual_seed(_seed(self.arm, self.rep, year, "torch"))
        nrng = np.random.default_rng(_seed(self.arm, self.rep, year, "np"))
        hprev = state.aux_patch.get("h")
        cprev = state.aux_patch.get("c")
        G1p = np.zeros((Ptot, S), np.float64)
        Yp = np.zeros((Ptot, S, len(nm.GROW_T)), np.float64)
        u_dem = np.zeros((Ptot, S), np.float64)  # learned correction logit g
        pabs = np.zeros((Ptot, S), np.float64)
        fire = np.zeros(Ptot)
        rec_mu = np.zeros(Ptot)
        rec_al = np.zeros(Ptot)
        hnew = np.zeros((Ptot, m.dh), np.float32) if m.lstm_on else None
        cnew = np.zeros((Ptot, m.dh), np.float32) if m.lstm_on else None
        rec_store = []
        grass_o = np.zeros((Ptot, 3), np.float64)
        with torch.no_grad():
            clim_t = torch.nan_to_num((torch.from_numpy(cw).to(dev) - N.clim_m) / N.clim_s)
            stat = torch.from_numpy(self.stat).to(dev)
            stat[:, 1:] = torch.nan_to_num((stat[:, 1:] - N.stat_m[1:]) / N.stat_s[1:])
            z_c = m.clim(clim_t, stat)
            dz_c = clim_t[:, -1, m.dz_idx]
            dry_c = clim_t[:, -1, m.dry_idx]
            for b0 in range(0, Ptot, PB):
                sl = slice(b0, min(b0 + PB, Ptot))
                tk = torch.from_numpy(tokf[sl]).to(dev)
                ty = torch.from_numpy(ptyp[sl]).to(dev)
                cy = torch.from_numpy(pc_[sl]).to(dev)
                mk = torch.from_numpy(pmask[sl]).to(dev)
                gf = (torch.from_numpy(GF[sl]).to(dev) - N.grass_m) / N.grass_s
                ps = (torch.from_numpy(PS[sl]).to(dev) - N.pscal_m) / N.pscal_s
                ci = torch.from_numpy(ci_p[sl]).to(dev)
                z = z_c[ci]
                if m.lstm_on:
                    if hprev is None:
                        hc = m.initial_state(tk, ty, mk)
                    else:
                        hc = (
                            torch.from_numpy(hprev[sl]).to(dev),
                            torch.from_numpy(cprev[sl]).to(dev),
                        )
                    h = hc[0]
                else:
                    hc, h = None, None
                e, p = m.encode(N.tok(tk, ty), ty, cy, mk, gf, ps, z, h)
                u = m.tree_ctx(e, p, h, z)
                G1, _ = m.g_sample(u, gen)
                G1n = G1.double().cpu().numpy()
                G1p[sl] = G1n
                # counter for the growth conditioning (the exact SH2 rule, incl. the age-1 reset, is
                # applied on CPU
                # below and asserted; printed trees are never age 1, so the two agree)
                c1 = torch.where(G1 < 0, cy + 1, torch.zeros_like(cy))
                mu, ls, _ = m.grow_params(u, G1, c1, dz_c[ci])
                yn = mu + torch.exp(ls) * torch.randn(mu.shape, generator=gen, device=dev)
                Yp[sl] = (yn * N.grow_s + N.grow_m).double().cpu().numpy()
                x = torch.cat(
                    [
                        u,
                        (torch.sign(G1) * torch.log1p(G1.abs() / 10.0))[..., None],
                        m.c_emb(c1.clamp(0, nm.NC)),
                    ],
                    -1,
                )
                u_dem[sl] = m.d_trunk(x)[..., 0].double().cpu().numpy()
                pabs[sl] = torch.sigmoid(m.absent(u)[..., 0]).double().cpu().numpy()
                pc = m.patch_ctx(p, h, z, gf, ps, dry_c[ci])
                fire[sl] = m.fire_f(pc).double().cpu().numpy()
                mu_r, al_r = m.rcount_params(pc)
                rec_mu[sl] = mu_r.double().cpu().numpy()
                rec_al[sl] = al_r.double().cpu().numpy()
                grass_o[sl] = m.grass(pc).double().cpu().numpy()
                rec_store.append((sl, pc, e, ty, mk))
                if m.lstm_on:
                    h2, c2 = m.advance(p, ps, z, hc)
                    hnew[sl] = h2.float().cpu().numpy()
                    cnew[sl] = c2.float().cpu().numpy()
        # ---------------------------------------------------------------- per-tree update (living
        # printed trees)
        G1 = G1p[pl_, slot]
        Y = Yp[pl_, slot]
        Age = t["Age"][li].astype(np.float64)
        c_prev = t["c"][li].astype(np.int64)
        c1 = nm.counter_next(c_prev, G1, Age)
        H1 = R["Height"] * np.exp(Y[:, 0])
        agb1 = R["agb"] * np.exp(Y[:, 1])
        vegc1 = R["vegc"] * np.exp(Y[:, 2])
        LAI1 = np.maximum(Y[:, 3], 0.0)
        fpc1 = np.clip(R["fpc_ind"] * np.exp(Y[:, 4]), 1e-8, 1.0)
        D95_1 = np.maximum(R["D95"] + Y[:, 5], 0.0)
        npp1, transp1 = Y[:, 6], np.maximum(Y[:, 7], 0.0)
        wscal1 = np.clip(Y[:, 8], 0.0, 1.0)
        W1 = np.maximum(np.expm1(Y[:, 9]), 0.0)
        tcols = [f"tstress_pft{k}" for k in range(nm.NTYPE)]
        cl1 = clim_y1.select(tcols).to_numpy().astype(np.float64)  # [C, 7] in state cell order
        ci_t = state.cell_index(t["Cell"][li])
        tdays = cl1[ci_t, np.clip(R["Type"], 0, nm.NTYPE - 1)]
        ms = rl.mortality_step(
            R["Type"], R["Wooddens"], Age, c_prev, G1, W1, tdays, int(flags_y1["rh_on"]), self.P
        )
        assert np.array_equal(ms["c"], c1), "counter mismatch vs SH2"
        hz = ms["mort"]
        hard = (c1 >= nm.NC) | (hz >= 1.0)
        g = u_dem[pl_, slot]
        hzc = np.clip(hz, 1e-6, 1 - 1e-6)
        lg = (np.log(hzc) - np.log1p(-hzc) + g) if m.offset else g
        pdem = np.where(hard if m.offset else (c1 >= nm.NC), 1.0, 1.0 / (1.0 + np.exp(-lg)))
        s = 1.0 / (1.0 + np.exp(-m.s_type.detach().cpu().numpy().astype(np.float64)))
        pdie = 1.0 - (1.0 - pdem) * (1.0 - s[np.clip(R["Type"], 0, nm.NTYPE - 1)] * fire[pl_])
        pdie = np.where(hard if m.offset else (c1 >= nm.NC), 1.0, pdie)
        keys = (t["Cell"][li], t["Patch"][li], t["Type"][li], t["ID"][li])
        ud = rand.uniform("nset_die", year, *keys)
        dead = ud < pdie
        ua = rand.uniform("nset_absent", year, *keys)
        hid = (~dead) & (ua < pabs[pl_, slot])
        upd = {
            k: t[k].copy()
            for k in [
                "Height",
                "agb",
                "vegc",
                "LAI",
                "fpc_ind",
                "D95",
                "Age",
                "c",
                "G",
                "W",
                "d_agb_prev",
                "npp",
                "transp",
                "wscal_mean",
                "mort_npp",
                "mort_age",
                "mort_water",
                "mort_temp",
                "mort",
            ]
        }
        for k, v in (
            ("Height", H1),
            ("agb", agb1),
            ("vegc", vegc1),
            ("LAI", LAI1),
            ("fpc_ind", fpc1),
            ("D95", D95_1),
            ("Age", Age + 1),
            ("c", c1),
            ("G", G1),
            ("W", W1),
            ("d_agb_prev", agb1 - R["agb"]),
            ("npp", npp1),
            ("transp", transp1),
            ("wscal_mean", wscal1),
            ("mort_npp", ms["mort_npp"]),
            ("mort_age", ms["mort_age"]),
            ("mort_water", ms["mort_water"]),
            ("mort_temp", ms["mort_temp"]),
            ("mort", hz),
        ):
            upd[k][li] = v
        isdead = np.zeros(n, bool)
        isdead[li] = dead
        hidden = t["hidden"].copy()
        hidden[li] = hid
        remove = t[
            "hidden"
        ].copy()  # trees hidden since the previous step leave silently (no submerged buffer)
        # ---------------------------------------------------------------- recruits
        alpha = np.maximum(rec_al, 1e-3)
        lam = nrng.gamma(1.0 / alpha, rec_mu * alpha)
        nrec = nrng.poisson(np.minimum(lam, 50.0))
        surv = ~dead & ~hid
        tree_cov = np.bincount(pl_[surv], weights=fpc1[surv], minlength=Ptot)
        rec = None
        if nrec.sum():
            rp = np.repeat(np.arange(Ptot), nrec)
            rec = self._recruits(rp, rec_store, X4, N, gen, nrng)
            ci = rp // npatch
            rec["Cell"] = self.cells[ci].astype(np.int16)
            rec["Patch"] = (rp % npatch).astype(np.int16)
            tree_cov += np.bincount(rp, weights=rec["fpc_ind"], minlength=Ptot)
        # ---------------------------------------------------------------- grass
        p0 = 1.0 / (1.0 + np.exp(-grass_o[:, 0]))
        zero = nrng.random(Ptot) < p0
        lai = np.where(
            zero,
            0.0,
            np.exp(
                grass_o[:, 1] + np.exp(np.clip(grass_o[:, 2], -5, 2)) * nrng.standard_normal(Ptot)
            ),
        )
        lai = np.minimum(lai, 20.0)
        gfpc = 1.0 - np.exp(-0.5 * lai)
        cap = np.maximum(1.0 - tree_cov, 0.0)
        self.n_clip["grass_capped"] += int((gfpc > cap).sum())
        grass = {
            "grass8_LAI": lai,
            "grass8_agb": nm.GRASS_K * lai,
            "grass8_fpc": np.minimum(gfpc, cap),
        }
        auxp = {"h": hnew, "c": cnew} if m.lstm_on else None
        return eng.StepOut(
            tree=upd,
            isdead=isdead,
            hidden=hidden,
            remove=remove,
            recruits=rec,
            grass=grass,
            aux_patch=auxp,
        )

    # ------------------------------------------------------------------------------------------
    # recruits
    def _recruits(self, rp, rec_store, X4, N, gen, nrng) -> dict:
        m, dev = self.model, self.dev
        R = len(rp)
        out = {
            k: np.zeros(R)
            for k in [
                "Type",
                "SLA",
                "Wooddens",
                "D95max",
                "minwscal",
                "Height",
                "Age",
                "c",
                "agb",
                "vegc",
                "LAI",
                "fpc_ind",
                "D95",
                "npp",
                "transp",
                "wscal_mean",
                "W",
                "G",
            ]
        }
        with torch.no_grad():
            for sl, pc, e, ty, mk in rec_store:
                sel = np.flatnonzero((rp >= sl.start) & (rp < sl.stop))
                if not len(sel):
                    continue
                loc = torch.from_numpy(rp[sel] - sl.start).to(dev)
                pcr = pc[loc]
                lt = m.r_type(pcr)
                rtyp = torch.multinomial(torch.softmax(lt.float(), -1), 1, generator=gen)[:, 0]
                cond = m.rec_cond(pcr, rtyp)
                tm, ts = N.trait_m[rtyp][:, :4], N.trait_s[rtyp][:, :4]
                x4s = (torch.from_numpy(X4[rp[sel]]).to(dev) - tm[:, None]) / ts[:, None]
                same = mk[loc] & (ty[loc] == rtyp[:, None])
                has = same.any(-1)
                a = m.r_copy_att(
                    torch.cat([e[loc], m.type_emb(rtyp)[:, None].expand(-1, e.shape[1], -1)], -1)
                )[..., 0].masked_fill(~same, -1e9)
                wc = (
                    torch.sigmoid(m.r_copyw(torch.cat([cond, has.float()[:, None]], -1))[..., 0])
                    * has.float()
                )
                use_copy = torch.rand(wc.shape, generator=gen, device=dev) < wc
                par = torch.multinomial(torch.softmax(a.float(), -1), 1, generator=gen)[:, 0]
                xc = x4s[torch.arange(len(par), device=dev), par] + torch.exp(
                    m.r_copy_ls[rtyp]
                ) * torch.randn((len(par), 4), generator=gen, device=dev)
                bg = m.r_bg(cond).view(-1, m.K, 9)
                kk = torch.multinomial(torch.softmax(bg[..., 0].float(), -1), 1, generator=gen)[
                    :, 0
                ]
                ar = torch.arange(len(kk), device=dev)
                xb = bg[ar, kk, 1:5] + torch.exp(bg[ar, kk, 5:9].clamp(-5, 2)) * torch.randn(
                    (len(kk), 4), generator=gen, device=dev
                )
                x4 = torch.where(use_copy[:, None], xc, xb)
                o = m.e_hage(torch.cat([cond, x4], -1))
                k = torch.exp(o[:, 0].clamp(-3, 5))
                rate = torch.exp(o[:, 1].clamp(-5, 5))
                h5 = torch.distributions.Gamma(k.float(), rate.float()).sample()
                H = 5.0 + h5.clamp(1e-3, 30.0)
                w = torch.softmax(o[:, 2:4], -1)
                comp = (torch.rand(len(w), generator=gen, device=dev) > w[:, 0]).long()
                lage = o[ar, 4 + comp] + torch.exp(o[ar, 6 + comp].clamp(-4, 2)) * torch.randn(
                    len(w), generator=gen, device=dev
                )
                cc = torch.multinomial(torch.softmax(m.e_c(cond).float(), -1), 1, generator=gen)[
                    :, 0
                ]
                r = m.e_rest(
                    torch.cat([cond, x4, (H[:, None] - 15.0) / 10.0, lage[:, None] / 3.0], -1)
                )
                mu2, ls2 = r.chunk(2, -1)
                En = mu2 + torch.exp(ls2.clamp(-6, 3)) * torch.randn(
                    mu2.shape, generator=gen, device=dev
                )
                Ev = (En * N.entry_s + N.entry_m).double().cpu().numpy()
                xr = (x4 * ts + tm).double().cpu().numpy()
                out["Type"][sel] = rtyp.cpu().numpy()
                out["SLA"][sel] = np.exp(xr[:, 0])
                out["Wooddens"][sel] = np.exp(xr[:, 1])
                out["D95max"][sel] = np.exp(xr[:, 2])
                out["minwscal"][sel] = np.clip(xr[:, 3], 1e-4, 1.0)
                out["Height"][sel] = H.double().cpu().numpy()
                out["Age"][sel] = np.maximum(np.round(np.exp(lage.double().cpu().numpy())), 1.0)
                out["c"][sel] = cc.cpu().numpy()
                out["agb"][sel] = np.exp(Ev[:, 0])
                out["vegc"][sel] = np.exp(Ev[:, 0] + Ev[:, 1])
                out["LAI"][sel] = np.maximum(Ev[:, 2], 0.0)
                out["fpc_ind"][sel] = np.clip(np.exp(Ev[:, 3]), 1e-8, 1.0)
                out["D95"][sel] = np.maximum(Ev[:, 4], 0.0)
                out["npp"][sel] = Ev[:, 5]
                out["transp"][sel] = np.maximum(Ev[:, 6], 0.0)
                out["wscal_mean"][sel] = np.clip(Ev[:, 7], 0.0, 1.0)
                out["W"][sel] = np.maximum(np.expm1(Ev[:, 8]), 0.0)
                out["G"][sel] = nm.islog(Ev[:, 9]) * 10.0
        typ = out["Type"].astype(np.int64)
        out["Type"] = typ.astype(np.int8)
        out["Longevity"] = rl.longevity_of(out["SLA"], typ, nrng, self.P)
        out["beta_root"] = rl.getbetaroot(out["D95max"], self.P)
        out["c"] = out["c"].astype(np.int8)
        out["d_agb_prev"] = np.zeros(R)
        for k in ("mort_npp", "mort_age", "mort_water", "mort_temp", "mort"):
            out[k] = np.zeros(R)
        out["isdead"] = np.zeros(R, bool)
        out["hidden"] = np.zeros(R, bool)
        out["ID"] = np.full(R, -1, np.int64)
        return out
