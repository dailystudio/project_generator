db = db.getSiblingDB(dbName);
db.createUser({
    user: userName,
    pwd: userPass,
    roles:[
        {
            role: "dbOwner" ,
            db: dbName
        },
    ]
});
