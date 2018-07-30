## IPFS Messaging server

This playbook installs a decentralized messaging server with [IPFS] (https://ipfs.io/) and [Orbit] (https://github.com/orbitdb), with HTTP basic authentication

Messaging code (index.js) is from origin-bridge/8a476fd1d82a367707bad21ec78a89d61577eec0

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

### Known issues
- npm deletes installed modules and/or create recursive symlinks in the `node_modules` directory. The root cause is something to do with npm symlinking modules to themselves while resolving a modules' dependency tree. Workaround is to delete the symlink and rerun the playbook.

### Future features

- allow automated configuring of peer nodes in the IPFS bootstrap list
- allow recording/setting of keypair/peerID (the peerID is derived from the public key)