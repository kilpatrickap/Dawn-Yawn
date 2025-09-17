# Dockerfile for the Villager Agent's Kali Environment

# 1. Start from the official Kali Linux base image
FROM kalilinux/kali-rolling

# 2. Set environment variable to allow non-interactive installations
ENV DEBIAN_FRONTEND=noninteractive

# 3. Update package lists and install the SSH server and common pentesting tools
#    The `&& rm -rf /var/lib/apt/lists/*` cleans up to keep the image smaller.
RUN apt-get update && apt-get install -y \
    openssh-server \
    nmap \
    dnsutils \
    net-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Configure the SSH Server to allow root login with a key
#    This is required for the agent's driver to connect.
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# 5. Create the .ssh directory for the root user
RUN mkdir -p /root/.ssh

# 6. Copy your PUBLIC SSH key into the container.
#    This authorizes your host machine to connect to the container via SSH.
#    It looks for a file named 'id_ecdsa.pub' in the same directory as the Dockerfile.
COPY id_ecdsa.pub /root/.ssh/authorized_keys

# 7. Set the correct permissions for the SSH key
RUN chmod 600 /root/.ssh/authorized_keys

# 8. Expose the SSH port
EXPOSE 22

# 9. This is the command that will run when the container starts.
#    It starts the SSH server in the foreground, which is exactly what the original driver expects.
CMD ["/usr/sbin/sshd", "-D"]