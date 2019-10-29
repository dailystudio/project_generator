const https         = require('https');
const fs            = require('fs');
const express       = require('express');
const bodyParser    = require('body-parser');
const cookieParser  = require('cookie-parser')();
const cors          = require('cors')({origin: true});

const ENABLE_HTTPS = 'enable-https';
const KEY_PATH = 'key-path';
const CERT_PATH = 'cert-path';
const CERT_PASS_PHRASE = 'cert-pass-phrase';
const SERVER_PORT = 'server-port';

var argv = require('minimist')(process.argv.slice(2));
console.log('application arguments:');
console.dir(argv);
console.log();

const app = express();

var port = 1045;
if (argv[SERVER_PORT]) {
    port = argv[SERVER_PORT];
}

app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());
app.use(cors);
app.use(cookieParser);
app.use(express.static(__dirname + '/public'));

var codebaseApi = require('./api/codebaseapi.js')(app);

if (argv[ENABLE_HTTPS]) {
    if (argv[CERT_PASS_PHRASE] == undefined) {
        console.warn('no pass phrase input. use --cert-pass-phrase to set password of cert');
    }

    if (argv[KEY_PATH] == undefined) {
        console.error('use --key-path to set path of key');
        process.exit(1);
    }

    if (argv[CERT_PATH] == undefined) {
        console.error('use --cert-path to set path of cert');
        process.exit(1);
    }

    var options = {
        key: fs.readFileSync(argv[KEY_PATH]),
        cert: fs.readFileSync(argv[CERT_PATH]),
        passphrase: argv[CERT_PASS_PHRASE],
        requestCert: false,
        rejectUnauthorized: false
    };

    var server = https.createServer(options, app);
    server.listen(port, function(){
        console.log("Working on port %d, through HTTPS protocol", port);
    });

} else {
    app.listen(port, function () {
        console.log("Working on port %d, through HTTP protocol", port);
    });
}

