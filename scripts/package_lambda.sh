#!/usr/bin/env bash
set -e

# 1) Prep build area
cd lambda_package
rm -rf build
mkdir -p build
mkdir -p build/kane_lambda

# 2) Install all requirements into build/python (ensure Linux-compatible binaries)
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is required to build Linux-compatible dependencies. Please install Docker." >&2
  exit 1
fi
echo "Building dependencies inside Docker container for Linux compatibility..."
docker run --rm --platform linux/amd64 \
  -v "$(pwd)/..":/var/task \
  -w /var/task/lambda_package \
  --entrypoint bash \
  public.ecr.aws/lambda/python:3.12 \
  -c "pip install -r ../requirements.txt --target build/python --upgrade"

# If dependencies installed into a python/ dir, move them to root
if [ -d build/python ]; then
  mv build/python/* build/
  rm -rf build/python
fi

# 3) Copy our code & creds
cp -r ../kane_lambda/* build/kane_lambda/
cp ../kane_lambda/__init__.py build/kane_lambda/
cp service_account.json build/

# 4) Clean up compiled and cache files to slim package
find build -type d -name '__pycache__' -exec rm -rf {} +
find build -type f -name '*.pyc' -delete

# 5) Zip it up, excluding caches
cd build
zip -r9 ../kane_lambda_package.zip . -x "*__pycache__*" "*.pyc"
cd ..

echo "✅ Built lambda_package/kane_lambda_package.zip" 