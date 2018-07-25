This installs geth (latest version in the ethereum PPA), using systemd for process management, along with ufw firewall rules and HTTP authentication for RPC access.

Ansible Notes:

- If python on the target machine is not accessible at the path /usr/bin/python, add `ansible_python_interpreter` as a host variable in the inventory file

ex. `host_name_or_ip           ansible_python_interpreter=/usr/bin/python3`


config settings are in deploy/config/full_node_config.yml

-----------------------------------

Security Group settings:

Inbound: SSH, 30303 (Ethereum ports) - both TCP (data) and UDP (peer discovery)

-----------------------------------

Resources:

How to run a full node: https://medium.com/mercuryprotocol/how-to-run-an-ethereum-node-on-aws-a8774ed3acf6
How to secure a full node: https://medium.com/coinmonks/securing-your-ethereum-nodes-from-hackers-8b7d5bac8986


-----------------------------------

Commands

ansible-playbook ethereum_full_node.yml -u ubuntu -i inventory -l <rinkeby | ropsten | mainnet> -v

-------------------------------------------------------------------------------------------------

Connectivity tests

curl -X POST \
    --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":83}'  \
    -i \
    -H 'Content-Type:application/json' \
    -H 'Accept:application/json' \
    -H 'Authorization:Basic <user>:<pass>' \
    http://127.0.0.1:8545


-----------------------------------

Operational tests (from Geth CLI - `getch attach`)


peer count should be greater than 1
> net.peerCount
6

eth.syncing should be true
> eth.syncing
{
  currentBlock: 3922035,
  highestBlock: 3922099,
  knownStates: 11714163,
  pulledStates: 11714163,
  startingBlock: 0
}

netstat -atn (TCP) and netstat -aun (UDP) should show port 3303


-----------------------------------
Http headers returned by geth

HTTP/1.1 200 OK
Access-Control-Allow-Headers: Origin, X-Requested-With, Content-Type, Accept
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: *
Content-Type: application/json
Date: Sun, 08 Jul 2018 19:40:58 GMT
Connection: keep-alive
Transfer-Encoding: chunked
