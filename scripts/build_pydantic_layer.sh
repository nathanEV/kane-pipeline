#!/usr/bin/env bash
set -e

# Build a Pydantic Lambda Layer for Python 3.12
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is required to build the Pydantic layer." >&2
  exit 1
fi

LAYER_DIR=layer_build
# Target site-packages directory inside the Lambda layer
PYTHON_TARGET=$LAYER_DIR/python/lib/python3.12/site-packages

# Clean up any previous build
rm -rf $LAYER_DIR
mkdir -p $PYTHON_TARGET

echo "Installing Pydantic into layer directory..."
docker run --rm --platform linux/amd64 \
  -v "$(pwd)":/var/task \
  -w /var/task \
  --entrypoint bash \
  public.ecr.aws/lambda/python:3.12 \
  -c "pip install pydantic pydantic_core --target $PYTHON_TARGET --upgrade"

echo "Pruning caches..."
find $PYTHON_TARGET -type d -name '__pycache__' -exec rm -rf {} +
find $PYTHON_TARGET -type f -name '*.pyc' -delete

echo "Zipping layer..."
cd $LAYER_DIR
zip -r9 ../pydantic-layer.zip python
cd ..

echo "✅ Built pydantic-layer.zip" 