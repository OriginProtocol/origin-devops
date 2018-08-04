## IPFS Messaging server

This playbook installs a decentralized messaging server with [IPFS](https://ipfs.io/) and [Orbit](https://github.com/orbitdb), with HTTP basic authentication

### Operation

1. Have an ubuntu 16.06 machine image
2. Set hosts for messaging server in `inventory` under the group *[all]*
3. Fill out the configuration in `messaging-config.yml`
4. Run the playbook: `ansible-playbook messaging_server.yml -u ubuntu -i inventory -v`

### Default external ports
- 9012: default IPFS websocket port
- 4001: IPFS swarm port

### Differences from "stock" IPFS
- `/ip4/0.0.0.0/tcp/<websocket port>/ws` added to Addresses.swarm
- `--enable-pubsub-experiment` CLI option enables pubsub

### Monitoring
Prometheus is used for monitoring the deployment, and an ansible role for installing exporters is included in the playbook. If the deployment does not use Prometheus, the `prometheus_exporters` role can be commented out

### Future features

- allow automated configuring of peer nodes in the IPFS bootstrap list
- allow recording/setting of keypair/peerID (the peerID is derived from the public key)