# Run this app locally

Clone the repo:
```
git clone https://github.com/plotly/dash-self-driving
cd dash-self-driving
```

Create a environment:
```
conda create -n dash-self-driving python=3.7
conda activate dash-self-driving
pip install -r requirements.txt
```

Run the app:
```
python app.py
```

## Redis

This app makes use of Flasking caching through redis. If you are running this app locally and don't have redis-server installed, install it:
```
sudo apt install redis-server
```

Ensure that the following environment variable is created: `REDIS_URL="redis://localhost:6379"`. There's many way to do it, one of them is to modify the `.bashrc` file (e.g. using `vim ~/.bashrc`) and add the following line:
```
export REDIS_URL="redis://localhost:6379"
```

Then, open a new terminal and run `redis-server`.


## Potential errors

If you run into the following error:
```
ImportError: libSM.so.6: cannot open shared object file: No such file or directory
```

Then, check out [this issue](https://github.com/NVIDIA/nvidia-docker/issues/864). Make sure that you install the correct libraries (possibly add `sudo` if needed):
```
apt-get update
apt-get install -y libsm6 libxext6 libxrender-dev
pip install opencv-python
```