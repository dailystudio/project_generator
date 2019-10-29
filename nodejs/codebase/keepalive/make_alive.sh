#!/bin/bash

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 server_path cert_pass"
  echo "    this will deploy a service in /etc/systemd with real server path."
  echo ""
  echo "    module_name:    the module name to be online"
  echo "    server_path:    the absolute path of server deployment"
  echo "    key_path:       the absolute path of server private-key"
  echo "    cert_path:      the absolute path of server certification"
  echo

  exit
}

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 [-options] -m MODULE -s SEVER_PATH -k KEY_PATH -c CERT_PATH"
  echo "    This script will deploy a Node.js application to run as a service after boot"
  echo ""
  echo "    -m MODULE:      the module name to be online"
  echo "    -s SEVER_PATH:  the absolute path of server deployment"
  echo "    -k KEY_PATH:    the absolute path of server private-key"
  echo "    -c CERT_PATH:   the absolute path of server certification"
  echo "    -t:             test outputs only"
  echo
}

function exit_abnormal {
	print_usage
	exit 1
}

test_outputs=false
test_dir="./outputs"

while getopts :m:s:k:c:thH opt; do
  case ${opt} in
    m)
		module=${OPTARG}
    	;;
    s)
		srvdir=${OPTARG}
	    ;;
    k)
		keypath=${OPTARG}
    	;;
    c)
		certpath=${OPTARG}
		;;
	t)
	    test_outputs=true
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

if [ -z "${module}" ] || [ -z "${srvdir}" ] || [ -z "${keypath}" ] || [ -z "${certpath}" ]; then
    echo "[ERROR] required options is missing."
    exit_abnormal
fi

echo "module: ${module}"
echo "server path: ${srvdir}"
echo "private-key path: ${keypath}"
echo "certification path: ${certpath}"

root_dir="/"

if [ "$test_outputs" = true ]; then
    root_dir="./outputs"
	echo "testing outputs only, files will be generated in ${root_dir} ..."

    if [ ! -d ${root_dir} ]; then
   	    mkdir ${root_dir}
    fi
fi

systemddir="${root_dir}/etc/systemd/system"
rsyslogdir="${root_dir}/etc/rsyslog.d"

srvtmpl="$module.service.templ"
logtmpl="$module.conf.templ"
srvdest="$module.service"
logdest="$module.conf"

echo "generate final service: $srvtmpl -> $srvdest"
sed "s/%server_path%/${srvdir//\//\\/}/g;s/%cert_path%/${certpath//\//\\/}/g;s/%key_path%/${keypath//\//\\/}/g" $srvtmpl > $srvdest
echo "generate rsyslog conf: $logtmpl -> $logdest"
sed "s/%server_path%/${srvdir//\//\\/}/g" $logtmpl > $logdest

echo "copy server to systemd conf directory: $systemddir"
if [ ! -d ${systemddir} ]; then
    mkdir -p ${systemddir}
fi
cp $srvdest $systemddir

if [ "$test_outputs" = false ]; then
    systemctl daemon-reload
    systemctl enable $srvdest
    systemctl stop $srvdest
    systemctl start $srvdest
    systemctl status $srvdest
    ps aux | grep node
fi

echo "copy conf to rsyslog directory: $rsyslogdir"
if [ ! -d ${rsyslogdir} ]; then
    mkdir -p ${rsyslogdir}
fi
cp $logdest $rsyslogdir

if [ "$test_outputs" = false ]; then
    systemctl restart rsyslog
fi