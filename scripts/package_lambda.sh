#!/usr/bin/env bash
set -e

# 1) Prep build area
cd lambda_package
rm -rf build
mkdir -p build
mkdir -p build/kane_lambda

# 2) Install all requirements into build/python
git_root=$(dirname "$BASH_SOURCE")
python3 -m pip install -r ../requirements.txt --target build/python --upgrade

# If dependencies installed into a python/ dir, move them to root
if [ -d build/python ]; then
  mv build/python/* build/
  rm -rf build/python
fi

# 3) Copy our code & creds
cp -r ../kane_lambda/* build/kane_lambda/
cp ../kane_lambda/__init__.py build/kane_lambda/
cp service_account.json build/

# 4) Zip it up
cd build
zip -r9 ../kane_lambda_package.zip .
cd ..

echo "✅ Built lambda_package/kane_lambda_package.zip" 