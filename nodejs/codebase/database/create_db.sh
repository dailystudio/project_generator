#!/bin/bash

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 [-options] -m MONGO_URL -u USER -p PASS -d DB_NAME"
  echo "    This script will create database in target MongoDB and create a dedicated admin user for it."
  echo ""
  echo "    -m MONGO_URL:       the MongoDB URL"
  echo "    -u USER:            the admin user's name"
  echo "    -p PASS:            the admin user's password"
  echo "    -d DB_NAME:         the database name"
  echo
}

function exit_abnormal {
	print_usage
	exit 1
}

while getopts :m:u:p:d:hH opt; do
  case ${opt} in
    m)
	    mongo_url=${OPTARG}
    	;;
    u)
      user=${OPTARG}
      ;;
    p)
      pass=${OPTARG}
    	;;
    d)
      database=${OPTARG}
    	;;
    h|H)
      print_usage
      exit 2
      ;;
    :)
	    echo "[ERROR] $0: -${OPTARG} requires an argument."
      exit_abnormal
      ;;
    *)
	    echo "[ERROR] $0: -${OPTARG} is unsuppported."
      exit_abnormal
      ;;
  esac
done

if [ -z "${database}" ]; then
    echo "[ERROR] required options is missing."
    exit_abnormal
fi

url=${mongo_url}
if [ -z "${mongo_url}" ]; then
    url="localhost:27017"
    echo "[WARN] no MongoDB url specified. Connecting to ${url}"
fi

if [ -z "${user}" ];  then
    user="${database}Owner"
    echo "[WARN] no user specified. Use database name [${user}]"
fi

if [ -z "${pass}" ];  then
    digits=16
    len=`expr ${digits} / 2`
    #code=`xxd -l${len} -ps /dev/urandom`
    pass=`cat /dev/urandom | base64 | fold -w ${digits} | head -n 1`
    echo "[WARN] no pass specified. Use database name [${pass}]"
fi

echo "mongo: [${url}]"
echo "database: [${database}]"
echo "|- username: [${user}]"
echo "\`- password: [${pass}]"

mongoshell="mongo"
if [ ! -x "$(command -v ${mongoshell})" ]; then
    echo "[ERROR] mongo Shell is NOT installed. Please install it first."
    exit_abnormal
fi

${mongoshell} ${mongo_url} \
  --eval "var userName=\"${user}\"; var userPass=\"${pass}\"; var dbName=\"${database}\"" \
  ./createuser.js

dbAuthFile=".db.auth"
echo "${user}:${pass}" > ${dbAuthFile}
