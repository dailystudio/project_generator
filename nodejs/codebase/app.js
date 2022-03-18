const https         = require('https');
const fs            = require('fs');
const express       = require('express');
const bodyParser    = require('body-parser');
const cookieParser  = require('cookie-parser')();
const cors          = require('cors')({origin: true});
const logger        = require('devbricksx-js').logger;

const ENABLE_HTTPS = 'enable-https';
const KEY_PATH = 'key-path';
const CERT_PATH = 'cert-path';
const CERT_PASS_PHRASE = 'cert-pass-phrase';
const SERVER_PORT = 'server-port';
const ENABLE_DB = 'enable-db'
const DB_NAME = 'db-name';
const DB_AUTH_FILE = 'db-auth-file';
const DB_CONN_URLS = 'db-conn-urls';
const DB_CONN_OPTS = 'db-conn-opts';

let argv = require('minimist')(process.argv.slice(2));

logger.enableDebugOutputs(argv);
logger.debug(`application arguments: ${JSON.stringify(argv, null, " ")}`);

const app = express();

let port = 1045;
if (argv[SERVER_PORT]) {
    port = argv[SERVER_PORT];
}

app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());
app.use(cors);
app.use(cookieParser);
app.use(express.static(__dirname + '/public'));

app.use(require('./api/codebaseapi.js'));

if (argv[ENABLE_DB]) {
    let dbOpts = {
        authFile: argv[DB_AUTH_FILE],
        database: argv[DB_NAME],
        connUrls: argv[DB_CONN_URLS],
        connOpts: argv[DB_CONN_OPTS],
    };

    async function useDatabaseApisAsync() {
        app.use(await require('./api/dabaseapi.js')(dbOpts));
    }

    useDatabaseApisAsync().catch(function (e) {
       logger.warn(`use database APIs failed: ${e}`)
    });
}

if (argv[ENABLE_HTTPS]) {
    if (argv[CERT_PASS_PHRASE] === undefined) {
        logger.warn('no pass phrase input. use --cert-pass-phrase to set password of cert');
    }

    if (argv[KEY_PATH] === undefined) {
        logger.error('use --key-path to set path of key');
        process.exit(1);
    }

    if (argv[CERT_PATH] === undefined) {
        logger.error('use --cert-path to set path of cert');
        process.exit(1);
    }

    let options = {
        key: fs.readFileSync(argv[KEY_PATH]),
        cert: fs.readFileSync(argv[CERT_PATH]),
        passphrase: argv[CERT_PASS_PHRASE],
        requestCert: false,
        rejectUnauthorized: false
    };

    let server = https.createServer(options, app);
    server.listen(port, function(){
        logger.info(`Working on port ${port}, through HTTPS protocol`);
    });

} else {
    app.listen(port, function () {
        logger.info(`Working on port ${port}, through HTTP protocol`);
    });
}

