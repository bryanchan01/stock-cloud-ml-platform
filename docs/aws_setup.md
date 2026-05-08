# AWS EC2 Setup

This guide uses EC2 directly to keep the project realistic for a one-person course project. It avoids managed services and does not require AWS credentials inside the codebase.

## Cost Controls

- Start with `t3.medium` for setup and smoke tests.
- Use `t3.large` only for larger Spark experiments.
- Stop or terminate the instance immediately after experiments.
- Keep EBS volumes modest, for example 30 GB for this project.
- Restrict SSH ingress to your own IP address.
- Never commit AWS access keys, `.pem` files, or credentials.
- Estimate cost before longer runs:

```bash
python -m src.experiments.cost_estimator --hours 2 --instance t3_large
```

As of the researched AWS T3 page, Linux on-demand pricing in `us-east-1` is approximately `0.0418 USD/hour` for `t3.medium` and `0.0835 USD/hour` for `t3.large`. Always check current AWS pricing before running.

## Launch EC2

Use the AWS console or AWS CLI:

1. Choose Ubuntu Server 24.04 LTS.
2. Choose `t3.medium` for initial validation.
3. Create or select an SSH key pair.
4. Create a security group with inbound SSH port `22` restricted to your IP.
5. Use a 30 GB gp3 EBS root volume.

Connect:

```bash
ssh -i your-key.pem ubuntu@your-ec2-public-dns
```

## Install Runtime

From the repository root on EC2:

```bash
bash scripts/setup_ec2.sh
```

Log out and back in so Docker group membership applies.

Manual equivalent:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git make python3 python3-pip python3-venv openjdk-17-jdk
```

Docker installation follows Docker's official Ubuntu apt repository flow:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## Run Locally On EC2

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
make smoke
make download TICKER_LIMIT=10
make features
make train MODEL=logistic_regression
make backtest
make benchmark
```

## Run With Docker On EC2

```bash
make docker-build
make docker-run
```

## Optional Spark Standalone Cluster

For a small demonstration, use one master and one or two workers in the same security group. Keep Spark ports closed to the public internet. Allow worker-to-master traffic only inside the security group.

On the master, start Spark standalone using a Spark distribution or the installed PySpark distribution's Spark scripts if available:

```bash
start-master.sh
```

On workers:

```bash
start-worker.sh spark://MASTER_PRIVATE_DNS:7077
```

Then run:

```bash
SPARK_MASTER=spark://MASTER_PRIVATE_DNS:7077 bash scripts/run_spark.sh
```

This cluster mode is optional. The core deliverable works in Spark local mode and Docker.

## Shutdown

When done:

```bash
sudo shutdown now
```

Then stop or terminate the instance from the AWS console. Terminate any unneeded volumes or elastic IP addresses.

