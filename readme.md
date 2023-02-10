# Livraison avant VA

cd armoor/..

conda env create -f armoor/environment.yml
conda activate armoor_env
python -m build

git clone https://github.com/OpenDrift/opendrift.git
cd opendrift/
pip install --no-deps -e .
cd ..

pip install -q ./dist/armoor-0.0.3-py3-none-any.whl
