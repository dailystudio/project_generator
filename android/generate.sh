#!/bin/bash

codebase_dir="com/dailystudio/codebase"
codebase_pkg="com.dailystudio.codebase"
codebase_name="Code Base"
codebase_name_code="CodeBase"

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 [-options] -n APP_NAME  -p PACKAGE_NAME"
  echo "    This script will generate a project from the templates in the codebase"
  echo ""
  echo "    -n APP_NAME:                     the application name"
  echo "    -p PACKAGE_NAME:                 the package name"
  echo "    -o OUTPUT_DIRECTORY:             the target directory of generated project"
  echo "    -h:                              display this message"
  echo
}

function exit_abnormal {
	print_usage
	exit 1
}

function renamePackage() {
  base_dir=""
  if [ "$*" != "" ] ; then
      base_dir="$*"
  fi
  anchor_dir=${PWD}

  echo "     [*]: Renaming packages in [${base_dir}] ..."

  cd ${base_dir}
  dest_dir=""
  IFS='.' read -ra packages <<< "$pkg_name"
  for i in "${packages[@]}"; do
      dest_dir=${dest_dir}/${i}
#      echo ${dest_dir}
      mkdir -p ${i}
      cd ${i}
  done
  cd ${anchor_dir}

#  echo "moving contents from ${base_dir}/${codebase_dir} to ${base_dir}/${dest_dir}/ ..."
  mv ${base_dir}/${codebase_dir}/* ${base_dir}/${dest_dir}/
  rm -rf ${base_dir}/${codebase_dir}/
}

function renameFiles() {
  echo "     [*]: Renaming files [${codebase_name_code}*] to [${app_name_code}*] ..."

  files=`find . -name "${codebase_name_code}*"`

  for f in "${files[@]}"; do
#    echo ${f}
    nf=${f/${codebase_name_code}/${app_name_code}}
#    echo "moving ${f} to ${nf}"
    mv ${f} ${nf}
  done
}

function squeezeAndCapitalizeString() {
  orig_str=$*

  new_str=""
  for i in ${orig_str}; do 
    tmp=`echo -n "${i:0:1}" | tr "[:lower:]" "[:upper:]"`; 
    new_str=${new_str}"${tmp}${i:1}"; 
  done  

  echo "${new_str}"
}

function alignSourceCodes() {
  src_pkg="${codebase_pkg//./\.}"
  dst_pkg="${pkg_name//./\.}"
  src_name="${codebase_name// /\ }"
  dst_name="${app_name// /\ }"

  echo "     [*]: Replacing [${codebase_pkg}] with [${pkg_name}] in source codes ..."
  LC_ALL=C find . -type f -exec sed -i "" "s/${src_pkg}/${dst_pkg}/g" {} +
  echo "     [*]: Replacing [${codebase_name_code}] with [${app_name_code}] in source codes ..."
  LC_ALL=C find . -type f -exec sed -i "" "s/${codebase_name_code}/${app_name_code}/g" {} +
  echo "     [*]: Replacing [${codebase_name}] with [${app_name}] in source codes ..."
  LC_ALL=C find . -type f -exec sed -i "" "s/${src_name}/${dst_name}/g" {} +
}


while getopts :n:p:o:hH opt; do
  case ${opt} in
    n)
      app_name=${OPTARG}
      ;;
    p)
      pkg_name=${OPTARG}
      ;;
    o)
      outputs=${OPTARG}
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


if [ -z "${app_name}" ] || [ -z "${pkg_name}" ]; then
    echo "[ERROR] required options is missing."
    exit_abnormal
fi

source_dir="${PWD}/codebase"
if [ ! -d "${source_dir}" ]; then
    echo "[ERROR] codebase directory does NOT exist."
    exit 1
fi

output_dir="./generated"
if [ ! -z "${outputs}" ]; then
  output_dir=${outputs}
fi

app_name_code=$(squeezeAndCapitalizeString ${app_name})

echo "----- Code Generation for Android project -----"
echo "Application name:    [${app_name}, code: ${app_name_code}]"
echo "Package name:        [${pkg_name}]"
echo "Output directory:    [${output_dir}]"

if [ ! -d "${output_dir}" ]; then
    echo "Output directory does NOT exist, creating it ..."
    mkdir -p ${output_dir}
fi

OLD_PWD=${PWD}

echo
echo "[STEP 1]: Copying the codebase ..."
cp -af ${source_dir}/* ${output_dir}/

echo "[STEP 2]: Refactoring package structure ..."
cd ${output_dir}
renamePackage "app/src/main/java"
renamePackage "app/src/androidTest/java"
renamePackage "app/src/test/java"
renameFiles

echo "[STEP 3]: Aligning source codes to new structure ..."
alignSourceCodes

cd ${OLD_PWD}
