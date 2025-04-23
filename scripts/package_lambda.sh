#!/bin/bash
set -e

# Create a temporary directory for packaging
rm -rf /tmp/lambda_package
mkdir -p /tmp/lambda_package

# Install dependencies into the package root
python3 -m pip install -r requirements.txt --target /tmp/lambda_package/ --upgrade

# Create the kane_lambda directory inside the package
mkdir -p /tmp/lambda_package/kane_lambda

# Copy the kane_lambda files to the package/kane_lambda directory
cp -r kane_lambda/* /tmp/lambda_package/kane_lambda/
cp kane_lambda/__init__.py /tmp/lambda_package/kane_lambda/

# Copy service account credentials
cp service_account.json /tmp/lambda_package/

# Navigate to the package directory
cd /tmp/lambda_package

# Create the zip file
zip -r9 /tmp/kane_lambda_package.zip .

# Return to the original directory
cd -

# Copy the zip file to the current directory
cp /tmp/kane_lambda_package.zip ./kane_lambda_package.zip

echo "Package created at kane_lambda_package.zip" 