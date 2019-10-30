#!/bin/bash

#codebase_dir="com/dailystudio/codebase"
#codebase_pkg="com.dailystudio.codebase"
codebase_name="Code Base"
codebase_name_code="codebase"
codebase_default_port="1045"
codebase_default_version="0.0.0"

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 [-options] -n APP_NAME  -e ENDPOINT_NAME"
  echo "    This script will generate a project from the templates in the codebase"
  echo ""
  echo "    -n APP_NAME:                     the application name"
  echo "    -e ENDPOINT_NAME:                the API endpoint name"
  echo "    -p PORT_NUMBER:                  the port number of the service"
  echo "    -v VERSION_NUMBER:               the start version number of the service"
  echo "    -o OUTPUT_DIRECTORY:             the target directory of generated project"
  echo "    -h:                              display this message"
  echo
}

function exit_abnormal {
	print_usage
	exit 1
}

function squeezeAndLowerString() {
  orig_str=$*

  new_str=""
  for i in ${orig_str}; do
    tmp=`echo -n "${i:0:1}" | tr "[:upper:]" "[:lower:]"`;
    new_str=${new_str}"${tmp}${i:1}";
  done

  echo "${new_str}"
}

function alignSourceCodes() {
  src=$1
  src_code="${src//./\.}"
  src_code="${src_code// /\ }"
#  echo "${src} -> ${src_code}"

  dst=$2
  dst_code="${dst//./\.}"
  dst_code="${dst_code// /\ }"
#  echo "${dst} -> ${dst_code}"

  echo "     [*]: Replacing [${src}] with [${dst}] in source codes ..."
  LC_ALL=C find . -type f -exec sed -i "" "s/${src_code}/${dst_code}/g" {} +
}

function renameFiles() {
  echo "     [*]: Renaming files [${codebase_name_code}*] to [${app_name_code}*] ..."

  files=`find . -name "${codebase_name_code}*"`

  for f in ${files[@]}; do
#    echo "processing [${f}] ..."
    nf=${f/${codebase_name_code}/${app_name_code}}
#    echo "moving ${f} to ${nf}"
    mv ${f} ${nf}
  done
}


while getopts :n:e:o:p:v:hH opt; do
  case ${opt} in
    n)
      app_name=${OPTARG}
      ;;
    e)
      endpoint_name=${OPTARG}
      ;;
    o)
      outputs=${OPTARG}
      ;;
    p)
      port=${OPTARG}
      ;;
    v)
      version=${OPTARG}
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

if [ -z "${app_name}" ] || [ -z "${endpoint_name}" ]; then
    echo "[ERROR] required options is missing."
    exit_abnormal
fi

source_dir="${PWD}/codebase"
if [ ! -d "${source_dir}" ]; then
    echo "[ERROR] codebase directory does NOT exist."
    exit 1
fi

OLD_PWD=${PWD}
cd ${source_dir}
find . -name "node_modules" -exec rm -rf "{}" \; 2>/dev/null
find . -name "package-lock.json" -exec rm -rf "{}" \; 2>/dev/null
cd ${OLD_PWD}

output_dir="./generated"
if [ ! -z "${outputs}" ]; then
  output_dir=${outputs}
fi

target_port=`date +%H%M`
if [ ! -z "${port}" ]; then
  target_port=${port}
fi

start_version=${codebase_default_version}
if [ ! -z "${version}" ]; then
  start_version=${version}
fi

app_name_code=$(squeezeAndLowerString ${app_name})

echo
echo "--------------- Code Generation for Android project ---------------"
echo "Application name:    [${app_name}, code: ${app_name_code}]"
echo "Endpoint name:       [${endpoint_name}]"
echo "Port number:         [${target_port}]"
echo "Start version        [${start_version}]"
echo "Output directory:    [${output_dir}]"
echo "-------------------------------------------------------------------"

OLD_PWD=${PWD}

echo
echo "[STEP 1]: Copying the codebase ..."
if [ ! -d "${output_dir}" ]; then
    echo "     [*]: Creating output directory ..."
    mkdir -p ${output_dir}
fi 
#cp -af ${source_dir}/* ${output_dir}/
cp -af ${source_dir}/{.[!.],}* ${output_dir}/

echo "[STEP 2]: Generating API structure ..."
cd ${output_dir}
renameFiles

echo "[STEP 3]: Aligning source codes to the new structure ..."
alignSourceCodes "${codebase_name_code}" "${app_name_code}"
alignSourceCodes "${codebase_name}" "${app_name}"
alignSourceCodes "${codebase_default_port}" "${target_port}"
alignSourceCodes "${codebase_default_version}" "${start_version}"


cd ${OLD_PWD}
