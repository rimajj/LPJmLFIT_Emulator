#!/bin/bash
# CONFIG_HOOK for /home/jamirp/lpjml-fit/scripts/clustered/clustered_run.sh (ADR 0342): lean transient output list.
exec /home/jamirp/.conda/envs/py311_new/bin/python "$(dirname "$(readlink -f "$0")")/clu_emu.py" hook "$1"
