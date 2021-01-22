const fs                = require('fs');
const { MongoClient }   = require("mongodb");
const ObjectId          = require('mongodb').ObjectID;
const logger            = require('devbricksx-js').logger;
const fileutils         = require('devbricksx-js').fileutils;
const requtils          = require('devbricksx-js').requtils;
const resputils         = require('devbricksx-js').resputils;

const DEFAULT_DATABASE = 'codebase';
const DEFAULT_AUTH_FILE = './database/.db.auth';
const DEFAULT_CONN_URLS = '127.0.0.1:27017';
const DEFAULT_CONN_OPTS = null;

module.exports = async function (dbOpts) {
    const modExports = {};

    const client = await connectMongoDb(dbOpts)

    modExports.getCollection = async function (req, res) {
        logger.info(`${__function}: get collection [${req.params.collection}]`);

        if (!requtils.checkParametersOrResponseError(req, res, [
            ['params', 'collection']
        ])) {
            return;
        }

        let collectionName = req.params.collection;

        const database = client.db();
        const collection = database.collection(collectionName);

        const data = await collection.find().toArray();
        logger.debug(`data: ${JSON.stringify(data)}`);

        let response = {
            code: 200,
            data: data
        };

        res.end(JSON.stringify(response));
    }

    modExports.addObjects = async function (req, res) {
        logger.info(`${__function}: add object to collection [${req.params.collection}]`);

        if (!requtils.checkParametersOrResponseError(req, res, [
            ['params', 'collection']
        ])) {
            return;
        }

        let collectionName = req.params.collection;

        let objects = req.body;
        logger.debug(`objects: ${JSON.stringify(objects)}`);

        if (!(objects instanceof Array)) {
            return resputils.responseError(res, 400,
                `body should contain an array of objects.`)
        }

        const database = client.db();
        const collection = database.collection(collectionName);

        const result = await collection.insertMany(objects);
        logger.debug(`${result.insertedCount} object(s) added.`)
        let response = {
            code: 200,
            count: result.insertedCount
        };

        res.end(JSON.stringify(response));
    }

    modExports.deleteObject = async function (req, res) {
        logger.info(`${__function}: delete object in collection [${req.params.collection}]`);

        if (!requtils.checkParametersOrResponseError(req, res, [
            ['params', 'collection'],
            ['params', 'id']
        ])) {
            return;
        }

        const docId = req.params.id
        const collectionName = req.params.collection;
        logger.debug(`collection: ${collectionName}, docId: ${docId}`);

        const database = client.db();
        const collection = database.collection(collectionName);
        const query = { _id : new ObjectId(docId) };

        const result = await collection.deleteOne(query);
        logger.debug(`${result.deletedCount} object(s) deleted.`)
        let response = {
            code: 200,
            count: result.deletedCount
        };

        res.end(JSON.stringify(response));
    }

    return modExports;
};


async function connectMongoDb(dbOpts) {
    logger.debug(`connect database: opts = ${JSON.stringify(dbOpts)}`);

    let database = DEFAULT_DATABASE;
    if (dbOpts && dbOpts.database) {
        database = dbOpts.database
    }

    let authFile = DEFAULT_AUTH_FILE;
    if (dbOpts && dbOpts.authFile) {
        authFile = dbOpts.authFile
    }

    let connUrls = DEFAULT_CONN_URLS
    if (dbOpts && dbOpts.connUrls) {
        connUrls = dbOpts.connUrls
    }

    let connOpts = DEFAULT_CONN_OPTS
    if (dbOpts && dbOpts.connOpts) {
        connOpts = dbOpts.connOpts
    }

    logger.debug(`database: ${database}`);
    logger.debug(`|- auth file: ${authFile}`);
    logger.debug(`|- urls: ${connUrls}`);
    logger.debug(`\`- opts: ${connOpts}`);

    let auth = ""
    if (fs.existsSync(authFile)) {
        let authContent = fileutils.strFromFile(authFile).trim();
        if (authContent && authContent !== "") {
            let authParts = authContent.split(":");

            auth=`${encodeURIComponent(authParts[0])}:${encodeURIComponent(authParts[1])}`
            logger.info(`database authentication found in ${authFile}: [${auth}]`)
        }
    }

    let uri = "";
    if (auth !== "") {
        uri += auth;
        uri += '@';
    }

    uri += connUrls;
    uri += '/';
    uri += database;

    if (connOpts) {
        uri += '?';
        uri += connOpts;
    }

    let connUri = `mongodb://${uri}`
    logger.debug(`MongoDB Uri: ${connUri}`);

    let client = new MongoClient(connUri, {
        useNewUrlParser: true,
        useUnifiedTopology: true
    });

    try {
        await client.connect();
        await client.db(database).command({ ping: 1 });
        logger.info(`[${database}] connected.`);
    } catch (e) {
        logger.error(`failed to connect: ${database}.`);
        await client.close();

        client = null
    }

    return client;
}
