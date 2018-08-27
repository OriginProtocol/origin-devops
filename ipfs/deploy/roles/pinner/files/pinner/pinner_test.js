// Requires:
//  - two configuration files, one for each simulated IPFS node / pinner
//  - blockchain, two IPFS nodes, pinner sqlite DBs must all be blank

// suppress console.test_log() from other files
console.test_log = console.log
console.log = function() {}

const Web3 = require('web3')
const Origin = require('origin')
const ipfsAPI = require('ipfs-api')
const request = require('request-promise')

const sqlite3 = require('sqlite3').verbose()
const assert = require('assert')
const { execSync } = require('child_process')
const execAsync = require('child_process').exec

const web3Provider = new Web3.providers.HttpProvider('http://localhost:8545')
const web3 = new Web3(web3Provider)

const configA = require("./config/config_local_test_a.json")
const configB = require("./config/config_local_test_b.json")

if(configA['grace_period'] !== configB['grace_period']) {
    throw("Error: the two configs must have the same grace period")
}
const gracePeriod = parseInt(configA['grace_period'])

// const ipfsA = ipfsAPI(configA['ipfs_domain'], '5001', { protocol: 'http' })
// const ipfsB = ipfsAPI(configB['ipfs_domain'], '5002', { protocol: 'http' })

const dbA = new sqlite3.Database(configA['db_file'])
const dbB = new sqlite3.Database(configB['db_file'])

const runPinnerACmd = "source ve/bin/activate;python ipfs_pinner.py -c config/config_local_test_a.json"
const runPinnerBCmd = "source ve/bin/activate;python ipfs_pinner.py -c config/config_local_test_b.json"
const numOriginA = 4
const numOriginB = 5
const numNonOriginA = 1
const numNonOriginB = 2

const contracts = {
  listingsRegistryContract: {999: {address: "0x8f0483125fcb9aaaefa9209d8e9d7b9c8b9fb90f"}},
  listingsRegistryStorageContract: {999: {address: "0xf25186b5081ff5ce73482ad761db0eb0d25abfbf"}},
  purchaseContract: {999: {address: "0x345ca3e014aaf5dca488057592ee47305d9b3e10"}},
  userRegistryContract: {999: {address: "0x2c2b9c9a4a25e24b174f26114e8926a9f2128fe4"}}
}

const originConfigA = {
  ipfsDomain: configA['ipfs_domain'],
  ipfsApiPort: configA['ipfs_port'],
  ipfsGatewayPort: '8080',
  ipfsGatewayProtocol: 'http',
  web3,
  contractAddresses: contracts
}

const originConfigB = {
  ipfsDomain: configB['ipfs_domain'],
  ipfsApiPort: configB['ipfs_port'],
  ipfsGatewayPort: '8080',
  ipfsGatewayProtocol: 'http',
  web3,
  contractAddresses: contracts
}


const originA = new Origin(originConfigA)
const originB = new Origin(originConfigB)

const wait = ms => new Promise(resolve => setTimeout(resolve, ms))

async function createListings(instance, num, origin) {
    async function createListing(originInstance, listingData, schema) {
        const transaction = await originInstance.listings.create(listingData, "for-sale")
        const receipt = transaction.transactionReceipt
        const index = receipt.events.NewListing.returnValues['_index']
        const listing = await originInstance.listings.getByIndex(index)
        const ipfsHash = listing.ipfsHash
        return ipfsHash
    }

    let hashes = []

    console.test_log("Creating " + num + " Origin listings using IPFS instance " + instance)
    for (i = 0; i < num; i++) {
        const listingData = {
          name: "listing " + i + " A",
          category: "For Sale",
          location: "San Francisco, CA",
          description:
            "Lasers",
          pictures: [],
          price: 1.1
        }
        res = await createListing(origin, listingData, 'for-sale')
        hashes.push(res)
    }
    
    console.test_log(hashes.length + " listing hashes in IPFS " + instance + ": " + hashes)

    return hashes
}


async function uploadContent(instance, num, origin) {
    let hashes = []

    console.test_log("Uploading " + num + " non-Origin pieces of content to IPFS instance " + instance)
    for (i = 0; i < num; i++) {
        res = await origin.ipfsService.submitFile({
          name: "non-listing " + i + " " + instance,
          category: "For Sale",
          location: "San Francisco, CA",
          description:
            "Lasers",
          pictures: [],
          price: 1.1
        })
        hashes.push(res)
    }

    console.test_log(hashes.length + " non-listing hashes in IPFS " + instance + ": " + hashes)
    return hashes

}



function getIpfsPins(config) {
    return new Promise(function(resolve, reject) {
        request({
            method: 'GET',
            uri: "http://" + config['ipfs_domain'] + ":" + config['ipfs_port'] + "/api/v0/pin/ls",
            json: true
        }).then(function(res) {
            let pins = res["Keys"]
            ipfsHashes = Object.keys(pins)
            resolve(ipfsHashes)
        }).catch((err) => {
            throw("Error retrieving pins: " + err)
        })
    })
}

function runPinner(instance, cmd) {
    console.test_log("running pinner: " + cmd)
    execSync(cmd, function(err, stdout, stderr) {
        if (!err) {
            console.test_log("Ran pinner on instance " + instance)
            console.test_log(stdout)
        } else {
            console.error("Error running pinner on instance " + instance + ": " + err)
            console.error(stderr)
        }
    })
}

function arrayEqual(array1, array2) {
    var equal = (array1.length === array2.length && array1.sort().every(function(value, index) { return value === array2.sort()[index]}))
    return equal
}



function readDbPins(db) {
    console.test_log("reading db pins from: " + db.filename)
    return new Promise(function(resolve, reject) {
        db.all("SELECT * FROM db_pins", function(err, rows) {
            if (err) {
                throw err
            }
            let dbHashes = rows.map(row => row['content_hash'])
            resolve(dbHashes)
        })
    })
}


async function testPinners() {
    // Create listings using origin-js, uploading some to IPFS1 and others to IPFS2
    let hashesOriginA = await createListings("A", numOriginA, originA)
    let hashesOriginB = await createListings("B", numOriginB, originB)
    
    // Upload non-origin content to IPFS1 and IPFS2
    let hashesNonOriginA = await uploadContent("A", numNonOriginA, originA)
    let hashesNonOriginB = await uploadContent("B", numNonOriginB, originB)

    // Assert IPFS pins: should contain all content that was uploaded to the node
    var ipfsHashesA = await getIpfsPins(configA)
    var hashes = hashesOriginA.concat(hashesNonOriginA)
    hashes.map(function(hash) {
        if (ipfsHashesA.indexOf(hash) == -1) {
            assert.fail("pins in IPFS A do not contain all hashes: " + hashes)
        }
    }) 
    console.test_log("IPFS A contains all uploaded content (Origin + non-Origin)")

    var ipfsHashesB = await getIpfsPins(configB)
    var hashes = hashesOriginB.concat(hashesNonOriginB)

    hashes.map(function(hash) {
        if (ipfsHashesB.indexOf(hash) == -1) {
            assert.fail("pins in IPFS B do not contain all hashes: " + hashes)
        }
    }) 
    console.test_log("IPFS B contains all uploaded content (origin + non-origin)")

    // Run pinners
    runPinner("A", runPinnerACmd)
    runPinner("B", runPinnerBCmd)

    // assert DB state: there should be entries corresponding to non-origin content
    // const db = new sqlite3.Database('pinner.db')
    var dbPinsA = await readDbPins(dbA)
    if (!arrayEqual(dbPinsA, hashesNonOriginA)) {
        assert.fail("pins in DB A (" + dbPinsA + ") do not coresspond to non-Origin hashes in A (" + hashesNonOriginA + ")")
    }
    // console.test_log(hashesNonOriginA)
    var dbPinsB = await readDbPins(dbB)
    // console.test_log(hashesNonOriginB)
    if (!arrayEqual(dbPinsB, hashesNonOriginB)) {
        assert.fail("pins in DB B (" + dbPinsB + ") do not coresspond to non-Origin hashes in B (" + hashesNonOriginB + ")")
    }

    console.test_log("pins in both DBs correspond to non-Origin hashes")

    // assert IPFS pins: all origin content should now exist on both IPFS servers
    let allOriginHashes = hashesOriginA.concat(hashesOriginB)
    var ipfsHashesA = await getIpfsPins(configA)
    var ipfsHashesB = await getIpfsPins(configB)
    allOriginHashes.map(function(originHash) {
        if (ipfsHashesA.indexOf(originHash) == -1) {
            assert.fail("Not all origin hashes are in IPFS A post-pinning")
        }
        if (ipfsHashesA.indexOf(originHash) == -1) {
            assert.fail("Not all origin hashes are in IPFS B post-pinning")
        }
    })

    console.test_log("all Origin hashes are pinned in both IPFS nodes")

    // Pause to wait for grace period to expire
    console.test_log("waiting " + gracePeriod + " seconds for grace period to expire")
    await wait((gracePeriod * 1000) + 5000)

    // Run pinners a second time
    runPinner("A", runPinnerACmd)
    runPinner("B", runPinnerBCmd)

    // assert IPFS pins: both nodes have only origin content pinned
    var ipfsHashesA = getIpfsPins(configA)
    var ipfsHashesB = getIpfsPins(configB)
    var hashes = hashesOriginA.concat(hashesOriginB)
    if (!arrayEqual(ipfsHashesA, allOriginHashes)) {
        assert("IPFS A does not have all origin content pinned after second run")
    }
    if (!arrayEqual(ipfsHashesB, allOriginHashes)) {
        assert("IPFS B does not have all origin content pinned after second run")
    }

    console.test_log("ONLY Origin hashes are pinned in both IPFS nodes")

    // assert DB state: there should be entries corresponding to non-origin content
    // const db = new sqlite3.Database('pinner.db')
    var dbPinsA = await readDbPins(dbA)
    if (!arrayEqual(dbPinsA, [])) {
        assert("DB A should be empty after the second pinner run, but contains: " + dbPinsA)
    }
    
    var dbPinsB = await readDbPins(dbB)
    if (!arrayEqual(dbPinsB, [])) {
        assert("DB B should be empty after the second pinner run, but contains: " + dbPinsB)

    }

    console.test_log("Both DBs are empty after grace period expiration")

    console.test_log("--------------------")
    console.test_log("TEST RUN OK.")

}






testPinners()