const express      = require('express');
const codebaseV1   = require('./v1/codebase.js');

const codebaseApiRouter = express.Router({});

codebaseApiRouter.get('/v1/codebase/echo', (req, res) => {
    return codebaseV1.echo(req, res);
});

codebaseApiRouter.post('/v1/codebase/echoUpload', (req, res) => {
    return codebaseV1.echoUpload(req, res);
});

module.exports = codebaseApiRouter;