#! /usr/bin/env python3
import argparse
import logging
import sys
import os
import json
import sqlite3
import requests
import time
import re

from web3 import Web3, HTTPProvider, WebsocketProvider
from web3.contract import Contract
from web3.middleware import geth_poa_middleware # required for POA i.e. Rinkeby
from eth_abi import decode_abi
from hexbytes import HexBytes
import requests
import ipfsapi
import base58

file_handler = logging.FileHandler(filename='pinner.log')
stdout_handler = logging.StreamHandler(sys.stdout)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [in %(pathname)s:%(lineno)d]: %(message)s',
    handlers=[stdout_handler, file_handler]
)

PID_FILE = 'pinner.pid'

MAINNET_NETWORK_ID = 1
ROPSTEN_NETWORK_ID = 3
RINKEBY_NETWORK_ID = 4
LOCAL_NETWORK_ID = 999

# Config defaults
# GRACE_PERIOD = 86400 # 1 day
# DB_FILE = 'pinner.db'
# LOG_FILE = 'pinner.log'
# LOG_LEVEL = 'INFO'
# IPFS_DOMAIN = 'http://127.0.0.1'
# IPFS_PORT = 5002
# PROVIDER_URL = 'http://127.0.0.1:8545'
# NETWORK_ID = 999
# CALL_CONTRACT_NAME = 'UnitListing'
# LISTINGS_REGISTRY_ADDRESS = '0x8f0483125fcb9aaaefa9209d8e9d7b9c8b9fb90f'
# EVENT_SIGNATURE = 'NewListing(uint256,address)'

GRACE_PERIOD = None
DB_FILE = None
LOG_FILE = None
LOG_LEVEL = None
IPFS_DOMAIN = None
IPFS_PORT = None
PROVIDER_URL = None
NETWORK_ID = None
CALL_CONTRACT_NAME = None
LISTINGS_REGISTRY_ADDRESS = None
EVENT_SIGNATURE = None

class Error(Exception):
    pass

class IPFSError(Error):
    pass

class EthereumError(Error):
    pass


############################################################
# AH: EventSource will be replaced by the event listener
############################################################
class EventSource:
    def __init__(self, provider, call_contract_name, contract_address, event_signature, network_id):
        self.contract_abis = {}
        self.provider = provider
        self.call_contract_name = call_contract_name
        self.contract_address = contract_address
        self.event_signature = event_signature
        self.network_id = network_id
        try:
            self.event_signature_types = re.search('\((.+?)\)', event_signature)[1].split(',')
        except Exception as e:
            logging.error(e)
            raise Error("Invalid event event_signature: %s" % (event_signature,))

        self.event_name_hash = provider.sha3(text=self.event_signature).hex()

    def get_contract_abi(self, contract_name):
        if self.contract_abis.get(contract_name):
            logging.debug("using cached contract abi for %s" % (contract_name,))
            return self.contract_abis[contract_name]

        with open("./contracts/{}.json".format(contract_name)) as f:
            contract_interface = json.loads(f.read())
            logging.debug("Loaded contract ABI: %s" % (f,))

        self.contract_abis[contract_name] = contract_interface['abi']
        return contract_interface['abi']

    def get_instance(self, contract_name, address):
        try:
            logging.debug("Getting contract: %s at address: %s" % (contract_name, address,))
            abi = self.get_contract_abi(contract_name)
            address = Web3.toChecksumAddress(address)
            contract = self.provider.eth.contract(abi=abi,
                                              address=address,
                                              ContractFactoryClass=Contract)
        except Exception as e:
            msg = "Exception while getting contract instance: %s - %s" % (type(e),e)
            logging.error(msg)
            raise EthereumError(msg)

        return contract

    def get_listing_ipfs_hash(self, payload):
        try:
            registry_index, address = decode_abi(self.event_signature_types, HexBytes(payload['data']))
            logging.debug("listing registry index: %s, UnitListing address: %s" % (registry_index, address,))
            listings_registry = self.get_instance("ListingsRegistry", self.contract_address)
            addr_in_listings_registry = listings_registry.call().getListingAddress(registry_index)
            logging.debug("[From ListingsRegistry] getListingAddress(%s) result: %s" % (registry_index, addr_in_listings_registry,))

            unit_listing = self.get_instance(self.call_contract_name, addr_in_listings_registry)

            bytes_ipfs_hash = unit_listing.call().ipfsHash()
            ipfs_hash = self.hex_to_base58(bytes_ipfs_hash)
        except Exception as e:
            msg = "Exception while retrieving listing data: %s - %s" % (type(e),e)
            logging.error(msg)
            raise EthereumError(msg)

        return ipfs_hash

    def hex_to_base58(self, byte32_hex):
        hash_hex = b'\x12 ' + byte32_hex
        return base58.b58encode(hash_hex)

    def fetch_events(self):
        if self.network_id in [ROPSTEN_NETWORK_ID, RINKEBY_NETWORK_ID]:
            return self.fetch_events_from_etherscan()
        else:
            return self.fetch_events_from_provider()

    def fetch_events_from_etherscan(self):
        # really shouldn't be a magic constant, but it's temporary until the event listener is implemented
        ETHERSCAN_API_KEY = "9BG9HPBASP3X95Z5ERF6TY99AXAE1XXSME"

        logging.info("Fetching events from Etherscan")

        if NETWORK_ID == ROPSTEN_NETWORK_ID:
            self.url = "https://api-ropsten.etherscan.io/api?module=logs&action=getLogs&fromBlock=0&toBlock=latest&topic0=%s&apikey=%s&address=%s" % (self.event_name_hash,ETHERSCAN_API_KEY,self.contract_address,)
        elif NETWORK_ID == RINKEBY_NETWORK_ID:
            self.url = "https://api-rinkeby.etherscan.io/api?module=logs&action=getLogs&fromBlock=0&toBlock=latest&topic0=%s&apikey=%s&address=%s" % (self.event_name_hash,ETHERSCAN_API_KEY,self.contract_address,)

        logging.debug("Etherscan url: %s" % (self.url,))

        hashes = set()

        res = requests.get(self.url)
        if res.status_code != 200:
            msg = "Exception while retrieving events via Etherscan API, non-200: %s" % (res.status_code,)
            logging.error(msg)
            raise EthereumError(msg)
        else:
            if "NOTOK" in res.text:
                msg = "Exception while retrieving events via Etherscan API, invalid API request: %s - URL: %s" % (res.text, res.url,)
                logging.error(msg)
                raise EthereumError(msg)
            else:
                res_json = json.loads(res.text)
                events = res_json['result']
                logging.debug("Received %s events from Etherscan" % (len(events),))
                if len(events):
                    for event in events:
                        ipfs_hash = self.get_listing_ipfs_hash(event)
                        hashes.add(str(ipfs_hash, encoding='utf-8'))

        return hashes

    def fetch_events_from_provider(self):
        logging.info("Fetching events from web3 provider")

        hashes = set()

        logging.info("creating filter")
        event_filter = self.provider.eth.filter({
            "topics": [self.event_name_hash],
            "fromBlock": 0,
            "toBlock": "latest"
        })

        process_events = False

        logging.info("getting filter entries")
        try:
            events = event_filter.get_all_entries()
        except Exception as e:
            msg = "Exception while retrieving events via JSON-RPC: %s - %s" % (type(e),e)
            logging.error(msg)
            raise EthereumError(msg)

        for event in events:
            ipfs_hash = self.get_listing_ipfs_hash(event)
            hashes.add(str(ipfs_hash, encoding='utf-8'))

        return hashes



def run_pinner():
    run_start_time = time.time()

    # initialize provider
    provider = Web3(HTTPProvider(PROVIDER_URL))
    provider.middleware_stack.inject(geth_poa_middleware, layer=0)

    # initialize connections
    conn = sqlite3.connect(DB_FILE)
    # conn.isolation_level = None # we don't want autocommit
    c = conn.cursor()
    ipfs_conn = ipfsapi.Client(IPFS_DOMAIN, IPFS_PORT)
    event_source = EventSource(provider, CALL_CONTRACT_NAME, LISTINGS_REGISTRY_ADDRESS, EVENT_SIGNATURE, NETWORK_ID)

    # load hashes from database
    c.execute("CREATE TABLE IF NOT EXISTS db_pins (content_hash VARCHAR(64), timestamp INTEGER)")
    c.execute("SELECT * FROM db_pins")
    conn.commit()
    db_pins_data = dict(c.fetchall())
    c.close()

    logging.info("%s db pins not yet seen in the blockchain" % (len(db_pins_data.keys()),))
    # logging.debug("db pins: %s" % (db_pins_data))
    logging.info("db pins: %s" % (db_pins_data))

    # fetch pins
    current_pins = None

    # AH: Only consider direct and recursive pins. Indirect pins cannot be
    # unpinned (the operation has to be done on the parent), so we only need to
    # store and unpin the recursive pins
    try:
        current_recursive_pins = set(ipfs_conn.pin_ls(type='recursive')['Keys'].keys())
        current_direct_pins = set(ipfs_conn.pin_ls(type='direct')['Keys'].keys())
        current_pins = current_recursive_pins.union(current_direct_pins)
    except ipfsapi.exceptions.Error as e:
        msg = "Exception while retrieving pins: %s - %s" % (type(e),e,)
        logging.error(msg)
        raise IPFSError(msg)

    logging.info("%s current pins in IPFS" % (len(current_pins),))
    logging.debug("current pins: %s" % (current_pins,))

    # TEMP for testing demo
    # sys.exit(0)

    # if there are pins that are in the DB but not in IPFS, those are stale 
    stale_pins = []
    for db_pin in db_pins_data.keys():
        if db_pin not in current_pins:
            stale_pins.append(db_pin)
 
    num_stale_pins = len(stale_pins)
    for stale_pin in stale_pins:
        del db_pins_data[stale_pin]

    logging.info("%s stale pins were removed (not currently in IPFS)" % (num_stale_pins,))

    # fetch Origin content hashes
    origin_content_hashes = None

    try:
        origin_content_hashes = event_source.fetch_events()
    except EthereumError as e:
        raise e

    logging.info("%s Origin content hashes in blockchain event logs" % (len(origin_content_hashes),))
    logging.debug("Origin content hashes: %s" % (origin_content_hashes,))

    # remove db pins that have now been seen in the blockchain
    for origin_hash in origin_content_hashes:
        if db_pins_data.get(origin_hash):
            del db_pins_data[origin_hash]

    # extract sets and pin / unpin:
    pinned_not_origin = current_pins.difference(origin_content_hashes)
    should_be_pinned = origin_content_hashes.difference(current_pins)


    logging.info("%s current pins are not origin related" % (len(pinned_not_origin),))
    db_hashes = db_pins_data.keys()
    num_new_db_hashes = 0
    num_removed_hashes = 0
    for ipfs_hash in pinned_not_origin:
        if ipfs_hash not in db_hashes:
            db_pins_data[ipfs_hash] = int(time.time())
            num_new_db_hashes += 1
        elif ipfs_hash in db_hashes:
            if(int(time.time()) - int(db_pins_data[ipfs_hash]) > GRACE_PERIOD):
                try:
                    ipfs_conn.pin_rm(ipfs_hash, recursive=True)
                    del db_pins_data[ipfs_hash]
                    num_removed_hashes += 1
                except Exception as e:
                    logging.error("Exception unpinning %s - (%s)" % (ipfs_hash, e))
                    # intrument

    logging.info("Added %s hashes to seen hashes" % (num_new_db_hashes,))
    logging.info("Unpinned %s hashes" % (num_removed_hashes,))

    logging.info("%s hashes to pin" % (len(should_be_pinned),))
    logging.info("to pin: %s" % (should_be_pinned,))
    # logging.debug("to pin: %s" % (should_be_pinned,))
    pinning_start_time = time.time()
    num_pinned_hashes = 0
    for ipfs_hash in should_be_pinned:
        try:
            pin_start_time = time.time()
            ipfs_conn.pin_add(ipfs_hash, recursive=False)
            num_pinned_hashes += 1
            logging.debug("%s pinned in %ss" % (ipfs_hash,int(time.time() - pin_start_time),))
        except Exception as e:
            logging.error("Exception pinning %s - (%s)" % (ipfs_hash, e))
            # intrument
    logging.info("pinned %s hashes in %ss" % (num_pinned_hashes, int(time.time() - pinning_start_time),))

    # write seen hashes back to DB
    logging.info("%s seen hashes after run" % (len(db_pins_data.keys()),))
    seen_hashes_tuples = [(ipfs_hash, time_seen) for ipfs_hash, time_seen in db_pins_data.items()]

    c = conn.cursor()
    c.execute("DELETE FROM db_pins")
    c.executemany("INSERT INTO db_pins VALUES (?,?)", seen_hashes_tuples)
    c.execute("SELECT COUNT(*) from db_pins")
    conn.commit()
    num_inserted_hashes = c.fetchone()[0]
    c.close()


    
    logging.info("%s seen hashes inserted into DB" % (num_inserted_hashes,))

    # end
    run_elapsed_time = time.time() - run_start_time
    logging.info('finished run in %s seconds' % (run_elapsed_time,))



if __name__ == '__main__':
    pid = os.getpid()
    if os.path.exists(PID_FILE):
        # check if pinner is actually running, or crashed
        f = open(PID_FILE, 'r')
        pid = int(f.readline())
        try:
            os.kill(pid, 0)
        except OSError:
            # remove stale PID file
            os.remove(PID_FILE)
        else:
            logging.info("Previous invocation of pinner still running (PID: %s) " % (pid,))
            sys.exit(0)
    f = open(PID_FILE, 'w')
    f.write(str(pid))
    f.close()
    

    parser = argparse.ArgumentParser(
        description="Pins content in the IPFS gateway if it's associated with " +
        "an Origin listing and unpins it if there's no associated listing.")
    parser.add_argument('-c', '--config', type=str, help="path to configuration file", required=True)
    args = parser.parse_args()
    logging.info("### Pinner run started ###")
    try:
        config = json.loads(open(args.config).read())
        GRACE_PERIOD = config['grace_period']
        DB_FILE = config['db_file']
        LOG_FILE = config['log_file']
        LOG_LEVEL = config['log_level']
        IPFS_DOMAIN = config['ipfs_domain']
        IPFS_PORT = config['ipfs_port']
        PROVIDER_URL = config['provider_url']
        NETWORK_ID = config['network_id']
        CALL_CONTRACT_NAME = config['call_contract_name']
        LISTINGS_REGISTRY_ADDRESS = config['listings_registry_address']
        EVENT_SIGNATURE = config['event_signature']
    except Exception as e:
        logging.error("Error reading configuration file: %s" % (e))
        sys.exit(1)

    logging.info("config: %s" % (config,))
    run_pinner()

    # remove PID file
    os.remove(PID_FILE)