const express      = require('express');

module.exports = async function (dbOpts) {
    const databaseV1 = await require('./v1/database.js')(dbOpts);
    const databaseApiRouter = express.Router({});

    databaseApiRouter.get('/v1/codebase/database/:collection',
        (req, res) => {
        return databaseV1.getCollection(req, res);
    });

    databaseApiRouter.put('/v1/codebase/database/:collection',
        (req, res) => {
        return databaseV1.addObjects(req, res);
    });

    databaseApiRouter.delete('/v1/codebase/database/:collection/:id',
        (req, res) => {
        return databaseV1.deleteObject(req, res);
    });

    return databaseApiRouter
}
