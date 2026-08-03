import oci
import json
import os

config = oci.config.from_file('~/.oci/config')
identity = oci.identity.IdentityClient(config)
network = oci.core.VirtualNetworkClient(config)
compute = oci.core.ComputeClient(config)
tenancy_id = config['tenancy']

# 1. Get Availability Domains
ads = identity.list_availability_domains(tenancy_id).data
ad_names = [ad.name for ad in ads]

# 2. Get Subnet ID
vcns = network.list_vcns(tenancy_id).data
if not vcns:
    subnet_id = "VCN_BULUNAMADI"
else:
    subnets = network.list_subnets(tenancy_id, vcn_id=vcns[0].id).data
    subnet_id = subnets[0].id if subnets else "SUBNET_BULUNAMADI"

# 3. Get Canonical Ubuntu 22.04 ARM Image for this region
images = compute.list_images(
    compartment_id=tenancy_id,
    operating_system='Canonical Ubuntu',
    operating_system_version='22.04',
    shape='VM.Standard.A1.Flex',
    sort_by='TIMECREATED',
    sort_order='DESC'
).data
image_id = images[0].id if images else "IMAGE_BULUNAMADI"

print(json.dumps({"ads": ad_names, "subnet": subnet_id, "image": image_id}))
