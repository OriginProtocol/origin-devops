## Messaging Persistence server

This playbook installs a persistence server for decentralized messaging, operating over websocket / secure websocket. The server uses [IPFS](https://ipfs.io) and [OrbitDB](https://github.com/orbitdb).

### Provisioning

1. Have an ubuntu 16.06 machine image
2. Set hosts for messaging server in `inventory` under the group *[all]*
3. Fill out the configuration in `messaging-config.yml`
4. Run the playbook: `ansible-playbook messaging_server.yml -u ubuntu -i inventory -v`

### SSL setup

[Certbot](https://certbot.eff.org/) is supported out of the box. The requirements are having a DNS entry for the server, as Certbot will not issue a certificate for an IP address. To install,

1. In the configuration, have `nginx_server_name` set to the certificate domain and `nginx_ssl` set to false
2. Provision as above
3. Run Certbot in the server CLI, only installing the certificate: `sudo certbot --nginx certonly`
4. set `nginx_ssl` to true and reprovision

### Operation

The messaging client will be configured with a `multiaddr` of the persistence server. The multiaddr depends on whether SSL and an accompanying domain name is used, and what value `nginx_ipfs_websocket_proxy_port` is set to. Examples:

- /dnsaddr/server.domain.tld/tcp/443/wss/ipfs/<peerID>
- /ip4/111.111.111/tcp/9999/ws/ipfs/<peerID>

The peer ID can be obstained from the IPFS config, located under `<messaging_directory>/ipfsrepo/config`

### Default external ports
- 80: port for Certbot certificate provisioning challenge response
- 443: default secure websocket port
- 4001: IPFS swarm port

### Monitoring
Prometheus is used for monitoring the deployment, and an ansible role for installing exporters is included in the playbook. If the deployment does not use Prometheus, the `prometheus_exporters` role can be commented out

### Future features

- allow recording/setting of keypair/peerID (the peerID is derived from the public key)