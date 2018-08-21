## IPFS Gateway

This playbook installs an [IPFS](https://ipfs.io/) gateway.


### Operation

1. Have an ubuntu 16.06 machine image
2. Set hosts for IPFS servers in `inventory` under the group *[gateways]*
3. Fill out the configuration in `config/gateway-config.yml`
4. Run the playbook: `ansible-playbook ipfs_gateway.yml -u ubuntu -i inventory -v`


### Default external ports
- 80: configured for Certbot challenge response (see "SSL" below)
- 4001: IPFS swarm
- 443: IPFS gateway
- 5002: IPFS API

### Monitoring
Prometheus is used for monitoring the deployment, and an ansible role for installing exporters is included in the playbook. If the deployment does not use Prometheus, the `prometheus_exporters` role can be commented out

### SSL

SSL is recommended and can be manually configured via [Certbot](certbot.eff.org), a free certificate provider managed by the EFF. The default NGINX configuration includes a route on port 80 for the Certbot challenge response request.

### Future features

- allow automated configuring of peer nodes in the IPFS bootstrap list
- allow recording/setting of keypair/peerID (the peerID is derived from the public key)

