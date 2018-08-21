## Ethereum Full Node

This playbook installs an Ethereum full node on MainNet, Rinkeby, or Ropsten


### Operation

1. Have an ubuntu 16.06 machine image
2. Set hosts for full node server in `inventory` under the groups corresponding to ethereum networks
3. Fill out the configuration in `config/full_node_config.yml`
4. Run the playbook: `ansible-playbook ethereum_full_node.yml -u ubuntu -i inventory -l <network> -v`


### Monitoring
Prometheus is used for monitoring the deployment, and an ansible role for installing exporters is included in the playbook. If the deployment does not use Prometheus, the `prometheus_exporters` role can be commented out
