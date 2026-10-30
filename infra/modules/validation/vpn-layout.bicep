targetScope = 'resourceGroup'

param networkIsolation bool
param clientPool string
param dnsSubnet string
param dnsSubnetName string
param gatewaySubnet string
param existingSubnetNames string[]
param existingSubnetPrefixes string[]
param vnetPrefixes string[]
param tenantId string
param audience string

func firstIp(prefix string) int => reduce(split(parseCidr(prefix).network, '.'), 0, (value, octet) => value * 256 + int(octet))
func lastIp(prefix string) int => reduce(split(parseCidr(prefix).broadcast, '.'), 0, (value, octet) => value * 256 + int(octet))
func ipv4Aligned(prefix string) bool => length(split(split(prefix, '/')[0], '.')) == 4 && split(prefix, '/')[0] == parseCidr(prefix).network

var required = !empty(clientPool) && !empty(dnsSubnet) && !empty(tenantId) && !empty(audience)
var validRanges = required ? ipv4Aligned(clientPool) && ipv4Aligned(dnsSubnet) && int(split(dnsSubnet, '/')[1]) >= 24 && int(split(dnsSubnet, '/')[1]) <= 28 && int(split(gatewaySubnet, '/')[1]) <= 27 : false
var poolSeparate = validRanges
  ? empty(filter(vnetPrefixes, prefix => firstIp(clientPool) <= lastIp(prefix) && lastIp(clientPool) >= firstIp(prefix)))
  : false
var dnsContained = validRanges
  ? !empty(filter(vnetPrefixes, prefix => firstIp(dnsSubnet) >= firstIp(prefix) && lastIp(dnsSubnet) <= lastIp(prefix)))
  : false
var dnsSeparate = validRanges
  ? empty(filter(existingSubnetPrefixes, prefix => firstIp(dnsSubnet) <= lastIp(prefix) && lastIp(dnsSubnet) >= firstIp(prefix)))
  : false

output validated bool = !networkIsolation
  ? fail('VPN Gateway requires networkIsolation=true.')
  : !required
    ? fail('VPN client pool, DNS subnet, tenant, and audience must be provided.')
    : !validRanges || !poolSeparate || !dnsContained || !dnsSeparate || contains(map(existingSubnetNames, name => toLower(name)), toLower(dnsSubnetName))
      ? fail('VPN requires aligned, non-overlapping IPv4 ranges: client pool outside VNet, dedicated DNS subnet at least /28 inside VNet, GatewaySubnet at least /27, and a unique DNS subnet name.')
      : true
