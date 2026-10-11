#!/bin/bash
# VERSION 1.0.6
# Install dependencies
sudo apt update
sudo apt install -y policykit-1 curl nftables

# Install the OpenVPN repository key used by the OpenVPN packages
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://packages.openvpn.net/packages-repo.gpg | sudo tee /etc/apt/keyrings/openvpn.asc

# Add the OpenVPN repository
echo "deb [signed-by=/etc/apt/keyrings/openvpn.asc] https://packages.openvpn.net/openvpn3/debian $(lsb_release -c -s) main" | sudo tee /etc/apt/sources.list.d/openvpn-packages.list
sudo apt update

# Install OpenVPN Connector setup tool
sudo apt install -y python3-openvpn-connector-setup

# Enable IP forwarding
sudo sed -i 's/#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/g' /etc/sysctl.conf
sudo sed -i 's/#net.ipv6.conf.all.forwarding=1/net.ipv6.conf.all.forwarding=1/g' /etc/sysctl.conf
sudo sysctl -p

# Configure NAT
sudo systemctl enable --now nftables
IF=$(ip route | grep -m 1 default | awk '{print $5}')
echo 'table ip nat4 {chain postrouting {type nat hook postrouting priority srcnat; policy accept; oif "'"$IF"'" masquerade;};}' | sudo tee /etc/nftables-msqrd.rules
echo 'table ip6 nat6 {chain postrouting {type nat hook postrouting priority srcnat; policy accept; oif "'"$IF"'" masquerade;};}' | sudo tee -a /etc/nftables-msqrd.rules
echo 'include "/etc/nftables-msqrd.rules"' | sudo tee -a /etc/nftables.conf
sudo systemctl reload nftables

# Run openvpn-connector-setup to import ovpn profile and connect to VPN.
# You will be asked to provide setup token, You can get it from the
# Linux Connector configuration page in CloudConnexa Portal.
sudo CLOUDCONNEXA_BASEURL='https://network-gateway.openvpn.com/network-gate/api/v1/profiles/' openvpn-connector-setup
