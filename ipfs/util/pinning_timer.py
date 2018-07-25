# records total time to pin a set of pins

# Steps to reset IPFS:
#   sudo service supervisor stop
#   rm -rf ~/.ipfs
#   ipfs init
#   sudo service supervisor start

# node can be reset without deleting .ipfs + reinitializing, by unpinning everything and issuing an ipfs repo gc
#   can verify with ipfs refs local before and after GC

# It could be that even with reseting the repo, there is still the DHT that exists for all the stuff that was just deleted

import time
import ipfsapi
import logging
import sys

file_handler = logging.FileHandler(filename='times.log')
stdout_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s [in %(pathname)s:%(lineno)d]: %(message)s',
        handlers=[stdout_handler, file_handler]
)

ipfs = ipfsapi.Client('http://127.0.0.1', 5001)

times = {}

start_time = time.time()
logging.info("Starting at: %s" % (start_time,))

pins = ["insert", "array", "of", "pins", "here"]

for pin in pins:
    # when running in background, output buffers are not flushed until program completes
    sys.stdout.flush()
    file_handler.flush()
    stdout_handler.flush()
    logging.info("running: %s" % (pin,))
    times[pin] = {}
    # start_dht_time = time.time()
    # providers = ipfs.dht_findprovs(pin)
    # elapsed_dht_time = time.time() - start_dht_time
    # times[pin]['dht'] = elapsed_dht_time
    # num_providers = len(list(filter(lambda provider: provider['Type'] == 4, providers)))
    # times[pin]['num_providers'] = num_providers
    start_pinning_time = time.time()
    ipfs.pin_add(pin, recursive=False)
    elapsed_pinning_time = time.time() - start_pinning_time
    times[pin]['pin'] = elapsed_pinning_time
    content = ipfs.cat(pin)
    times[pin]['size'] = len(content)
    logging.info("   result: %s" % (times[pin],))

logging.info("Run completed. Elapsed time: %s" % (time.time() - start_time))



