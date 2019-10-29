const codebaseV1   = require('./v1/codebase.js');

module.exports = function(app) {

    app.get('/v1/codebase/echo', (req, res) => {
        return codebaseV1.echo(req, res);
    });

    app.post('/v1/codebase/echoUpload', (req, res) => {
        return codebaseV1.echoUpload(req, res);
    });

};
