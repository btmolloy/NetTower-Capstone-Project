code/backEnd/utils/net.py

Purpose: Shared network parsing/validation/normalization helpers.
Inputs: strings (IPs, CIDRs, MACs), interface names.
Outputs: normalized/validated forms and boolean checks:

normalize_mac()

is_valid_ip()

is_valid_cidr()

ip_in_cidr()

(optional) interface listing helpers