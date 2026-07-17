#!/usr/bin/env bash
set -euo pipefail

# ponytail: fail closed until source rights/provenance support public refresh.
printf '%s\n' 'Public-site refresh is disabled pending source-rights review.' >&2
exit 1
