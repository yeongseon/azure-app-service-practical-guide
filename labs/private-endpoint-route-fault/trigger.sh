#!/bin/bash
# Add (or, with "restore", remove) a /32 route that sends traffic for the
# private endpoint address to an unused virtual-appliance address. DNS, the
# private DNS zone, and the endpoint approval are left untouched.
set -euo pipefail

RESOURCE_GROUP_NAME="${1:-}"
ACTION="${2:-fault}"
APPLIANCE_IP="10.50.3.4"

if [ -z "$RESOURCE_GROUP_NAME" ] || { [ "$ACTION" != "fault" ] && [ "$ACTION" != "restore" ]; }; then
    echo "Usage: $0 <RESOURCE_GROUP_NAME> [fault|restore]"
    exit 1
fi

route_table=$(az network route-table list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query "[0].name" \
    --output tsv | tr -d '\r')

if [ "$ACTION" = "restore" ]; then
    az network route-table route delete \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --route-table-name "$route_table" \
        --name pe-blackhole
    echo "Route removed. Allow about 3 minutes before probing /connect."
    exit 0
fi

endpoint_nic=$(az network private-endpoint list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query "[0].networkInterfaces[0].id" \
    --output tsv | tr -d '\r')
endpoint_ip=$(az network nic show \
    --ids "$endpoint_nic" \
    --query "ipConfigurations[0].privateIPAddress" \
    --output tsv | tr -d '\r')

az network route-table route create \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --route-table-name "$route_table" \
    --name pe-blackhole \
    --address-prefix "${endpoint_ip}/32" \
    --next-hop-type VirtualAppliance \
    --next-hop-ip-address "$APPLIANCE_IP" \
    --output none

echo "Route added: ${endpoint_ip}/32 -> VirtualAppliance ${APPLIANCE_IP} (nothing listens there)."
echo "Allow about 3 minutes, then probe /resolve and /connect and run verify.sh."
