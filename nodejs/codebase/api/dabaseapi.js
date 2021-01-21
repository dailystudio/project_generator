const express      = require('express');

module.exports = async function (dbOpts) {
    const databaseV1 = await require('./v1/database.js')(dbOpts);
    const databaseApiRouter = express.Router({});

    databaseApiRouter.get('/v1/codebase/database/list', (req, res) => {
        return databaseV1.list(req, res);
    });

    return databaseApiRouter
}
