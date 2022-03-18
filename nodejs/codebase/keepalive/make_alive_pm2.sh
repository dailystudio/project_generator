#!/bin/bash

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 [-options] -m MODULE -s SEVER_PATH"
  echo "    This script will deploy a application to run as a service after boot"
  echo ""
  echo "    -m MODULE:                       the module name to be online"
  echo "    -p PM2_NAME:                     the name used for PM2 startup"
  echo "    -s SEVER_PATH:                   the absolute path of server deployment"
  echo "    -k KEY0:VAL0 [KEY1:VAL1 ...]:    the key:value pairs for script arguments"
  echo "    -u USER:                         the user for executing the crontab"
  echo "    -t:                              test outputs only"
  echo
}

function exit_abnormal {
	print_usage
	exit 1
}

test_outputs=false
test_dir="./outputs"

while getopts :m:s:k:u:p:thH opt; do
  case ${opt} in
    m)
	    module=${OPTARG}
    	;;
    p)
	    pm2_name=${OPTARG}
    	;;
    s)
      srvdir=${OPTARG}
      ;;
    k)
      kv_pairs=${OPTARG}
    	;;
    u)
      user=${OPTARG}
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

if [ -z "${module}" ] || [ -z "${srvdir}" ]; then
    echo "[ERROR] required options is missing."
    exit_abnormal
fi

if [ -z "${pm2_name}" ] ]; then
    pm2_name = ${module}
fi

echo "module: ${module}"
echo "pm2_name: ${pm2_name}"
echo "server path: ${srvdir}"

IFS=',' kv_array=(${kv_pairs})
ncount=${#kv_array[@]}
i=0

sed_str="s/%server_path%/${srvdir//\//\\/}/g;s/%pm2_name%/${pm2_name//\//\\/}/g;"
if (( ${ncount} > 0 )); then
    echo "key-values: ${ncount}"
    for kv in ${kv_array[@]}; do
        key=$(echo ${kv%%:*} | xargs)
        val=$(echo ${kv#*:} | xargs)
        if [ ${i} == $((ncount - 1)) ]; then
            echo "\`- [${i}] Key: [${key}], Value: [${val}]"
        else
            echo "|- [${i}] Key: [${key}], Value: [${val}]"
        fi

        sed_str="${sed_str}""s/%${key}%/${val//\//\\/}/g;"
        i=$((i + 1))
     done
fi

echo "sed str: ${sed_str}"

if [ "$test_outputs" = true ]; then
  echo "testing outputs only, files will be generated in ${root_dir} ..."
fi

pm2tmpl="$module.config.js.templ"
pm2config="$module.config.js"

echo "generate pm2 configuration file: ${pm2tmpl} -> ${pm2config}"
su ${user} -c "cat ${pm2tmpl} | perl -pe \"${sed_str}\" > ${pm2config}"

if [ "$test_outputs" = false ]; then
  echo "stop application with pm2: ${pm2config}"
  su ${user} -c "pm2 stop ${pm2config}"
  echo "start application with pm2: ${pm2config}"
  su ${user} -c "pm2 start ${pm2config} --time"
  echo "save application to make it persistent after reboot: ${module}"
  su ${user} -c "pm2 save"

  echo "[DO pm2 startup only for the first time]"
  pm2 startup -u ${user} --hp "/home/${user}"
fi
