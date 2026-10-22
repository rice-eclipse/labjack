#!/bin/bash
# Robust reconnection script for Labjack Pi that handles r8152 driver quirks

CONNECTION_NAME="Labjack-Pi-Direct"
PI_IP="192.168.0.100"

echo "════════════════════════════════════════════════════════════════"
echo "  Reconnecting to Labjack Raspberry Pi via Ethernet"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script needs sudo privileges."
    echo "Please run with: sudo $0"
    exit 1
fi

echo "🔍 Step 1: Finding USB Ethernet interface..."
# Look for USB Ethernet interfaces (pattern: enp.*u[0-9])
ETH_INTERFACE=$(ip link show | grep -oP 'enp[0-9a-z]+u[0-9]+' | head -1)

if [ -z "$ETH_INTERFACE" ]; then
    echo "❌ No USB Ethernet adapter found!"
    echo ""
    echo "Please check:"
    echo "  • USB adapter is plugged in"
    echo "  • Try a different USB port"
    echo "  • Check dmesg for errors: sudo dmesg | tail -20"
    exit 1
fi

echo "   Found interface: $ETH_INTERFACE"
echo ""

echo "🔧 Step 2: Resetting r8152 driver..."
# Disconnect any active connection
nmcli connection down "$CONNECTION_NAME" 2>/dev/null

# Bring interface down
ip link set "$ETH_INTERFACE" down 2>/dev/null
sleep 1

# Reload the r8152 driver module
if lsmod | grep -q r8152; then
    echo "   Unloading r8152 module..."
    rmmod r8152 2>/dev/null
    sleep 2
    echo "   Reloading r8152 module..."
    modprobe r8152
    sleep 2
fi

echo ""
echo "🔌 Step 3: Bringing interface up..."
ip link set "$ETH_INTERFACE" up
sleep 2

echo ""
echo "🌐 Step 4: Activating NetworkManager connection..."

# Check if connection profile exists
if ! nmcli connection show "$CONNECTION_NAME" &> /dev/null; then
    echo "❌ Connection profile '$CONNECTION_NAME' not found!"
    echo ""
    echo "Please run the configuration script first:"
    echo "  sudo /home/wilsonh/Documents/GitHub/labjack/configure-ethernet-for-pi.sh"
    exit 1
fi

# Update the connection to use the current interface
echo "   Updating connection profile for $ETH_INTERFACE..."
nmcli connection modify "$CONNECTION_NAME" connection.interface-name "$ETH_INTERFACE" 2>/dev/null

# Activate the connection
echo "   Activating connection..."
nmcli connection up "$CONNECTION_NAME"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Failed to activate connection."
    echo ""
    echo "Trying alternative method..."
    
    # Try bringing it up manually
    ip link set "$ETH_INTERFACE" down
    sleep 1
    ip link set "$ETH_INTERFACE" up
    sleep 2
    
    nmcli connection up "$CONNECTION_NAME"
fi

echo ""
echo "⏳ Step 5: Waiting for link to stabilize..."
sleep 3

echo ""
echo "🧪 Step 6: Testing connectivity..."

if ping -c 3 -W 2 "$PI_IP" &> /dev/null; then
    echo "✅ Pi is reachable!"
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "  Reconnection Successful!"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    echo "You can now:"
    echo "  • SSH to Pi: ssh eclipsepi@$PI_IP (password: 1)"
    echo "  • Access WebSocket: ws://$PI_IP:2707"
    echo "  • Start Quonkboard and connect to: $PI_IP:2707"
    echo ""
    
    # Show link quality
    ping -c 3 "$PI_IP" | tail -2
else
    echo "⚠️  Connection activated but Pi is not responding to ping."
    echo ""
    echo "Troubleshooting steps:"
    echo "  1. Check Pi is powered on"
    echo "  2. Check ethernet cable is connected"
    echo "  3. Try unplugging/replugging the USB adapter"
    echo "  4. Run: sudo /home/wilsonh/Documents/GitHub/labjack/fix-r8152-link.sh"
    echo ""
    echo "Current interface status:"
    ip addr show "$ETH_INTERFACE" | grep -E 'state|inet '
    exit 1
fi
