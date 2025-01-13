#!/bin/bash

codebase_dir="com/dailystudio/codebase"
codebase_pkg="com.dailystudio.codebase"
codebase_name="Code Base"
codebase_name_code="CodeBase"

tmp_dir="./tmp"

function print_usage {
  echo "Usage:"
  echo
  echo "  $0 [-options] -n APP_NAME  -p PACKAGE_NAME"
  echo "    This script will generate a project from the templates in the codebase"
  echo ""
  echo "    -n APP_NAME:                     the application name"
  echo "    -p PACKAGE_NAME:                 the package name"
  echo "    -o OUTPUT_DIRECTORY:             the output directory of generated project"
  echo "    -t TARGET:                       the target: all, views [Android Views + XML], compose [Jetpack Compose]. Default is \"all\""
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

function removeModule() {
  local module_name="$1"  # 传入的模块名称
  local settings_file="settings.gradle"  # 指定文件名

  if [ ! -f "${settings_file}" ]; then
    echo "[ERROR]: ${settings_file} does not exist."
    return 1
  fi

  echo "[INFO]: Removing module: ${module_name} from ${settings_file} ..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "/include ':${module_name}'/d" "${settings_file}"
  else
    sed -i "/include ':${module_name}'/d" "${settings_file}"
  fi

  if [ $? -eq 0 ]; then
    echo "[INFO]: Successfully removed module: ${module_name}."
    return 0
  else
    echo "[ERROR]: Failed to remove module: ${module_name}."
    return 1
  fi
}

function renameFiles() {
  echo "     [*]: Renaming files [${codebase_name_code}*] to [${app_name_code}*] ..."

  files=`find . -name "${codebase_name_code}*"`

  for f in ${files[@]}; do
#    echo ${f}
    nf=${f/${codebase_name_code}/${app_name_code}}
#    echo "moving ${f} to ${nf}"
    mv ${f} ${nf}
  done
}

function squeezeAndCapitalizeString() {
  orig_str=`echo $* | tr -d "[:punct:]"`

  filter_str=${orig_str//-/\ }
  new_str=""
  for i in ${filter_str}; do 
    tmp=`echo -n "${i:0:1}" | tr "[:lower:]" "[:upper:]"`; 
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

function format_array {
  local input_array=("$@")
  local formatted=""
  for element in "${input_array[@]}"; do
    local temp=$(echo "${element:0:1}" | tr '[:lower:]' '[:upper:]')${element:1}
    formatted+="${temp}, "
  done

  echo "${formatted%??}"
}

target="all"
modules=("views" "compose")

while getopts :n:p:o:t:hH opt; do
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
    t)
      target=$(echo "${OPTARG}" | tr '[:upper:]' '[:lower:]')
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

if [[ "${target}" != "all" && "${target}" != "views" && "${target}" != "compose" ]]; then
    echo "[ERROR] Invalid target: [${target}]. Valid values are: [all, views, compose]."
    exit_abnormal
fi

case "${target}" in
  "views")
    modules=("views")
    ;;
  "compose")
    modules=("compose")
    ;;
  "all")
    modules=("views" "compose")
    ;;
esac

source_dir="${PWD}/codebase"
if [ ! -d "${source_dir}" ]; then
    echo "[ERROR] codebase directory does NOT exist."
    exit 1
fi

OLD_PWD=${PWD}
cd ${source_dir}
find . -name ".idea" -exec rm -rf "{}" \; 2>/dev/null
find . -name ".gradle" -exec rm -rf "{}" \; 2>/dev/null
find . -name "*.iml" -exec rm -rf "{}" \; 2>/dev/null
find . -name "build" -exec rm -rf "{}" \; 2>/dev/null
find . -name "local.properties" -exec rm -rf "{}" \; 2>/dev/null
cd ${OLD_PWD}

output_dir="./generated"
if [ ! -z "${outputs}" ]; then
  output_dir=${outputs}
fi

app_name_code=$(squeezeAndCapitalizeString ${app_name})

echo
echo "--------------- Code Generation for Android project ---------------"
echo "Application name:    [${app_name}, code: ${app_name_code}]"
echo "Package name:        [${pkg_name}]"
echo "Output directory:    [${output_dir}]"
echo "Targets:             [$(format_array ${modules[@]})]"
echo "-------------------------------------------------------------------"

OLD_PWD=${PWD}

rm -rf ${tmp_dir}
mkdir ${tmp_dir}

echo
echo "[STEP 1]: Copying the codebase ..."
if [ ! -d "${output_dir}" ]; then
    echo "     [*]: Creating output directory ..."
    mkdir -p ${output_dir}
fi 
#cp -af ${source_dir}/* ${output_dir}/
cp -af ${source_dir}/{.[!.],}* ${tmp_dir}/
if [[ ! " ${modules[@]} " =~ " views " ]]; then
    rm -rf ${tmp_dir}/app
fi
if [[ ! " ${modules[@]} " =~ " compose " ]]; then
    rm -rf ${tmp_dir}/app-compose
fi

echo "[STEP 2]: Refactoring package structure ..."
cd ${tmp_dir}
if [[ " ${modules[@]} " =~ " views " ]]; then
  renamePackage "app/src/main/java"
  renamePackage "app/src/androidTest/java"
  renamePackage "app/src/test/java"
else
  removeModule "app"
fi

if [[ " ${modules[@]} " =~ " compose " ]]; then
  renamePackage "app-compose/src/main/java"
  renamePackage "app-compose/src/androidTest/java"
  renamePackage "app-compose/src/test/java"
else
  removeModule "app-compose"
fi

renamePackage "core/src/main/java"
renamePackage "core/src/androidTest/java"
renamePackage "core/src/test/java"

renameFiles

echo "[STEP 3]: Aligning source codes to the new structure ..."
alignSourceCodes "${codebase_pkg}" "${pkg_name}"
alignSourceCodes "${codebase_name_code}" "${app_name_code}"
alignSourceCodes "${codebase_name}" "${app_name}"

cd ${OLD_PWD}

echo "[STEP 4]: Finalizing source codes into destination ..."
cp -af ${tmp_dir}/{.[!.],}* ${output_dir}/
rm -rf ${tmp_dir}
