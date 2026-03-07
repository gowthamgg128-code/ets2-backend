"""PC fingerprinting utility."""
import hashlib
import platform


def generate_pc_id() -> str:
    """
    Generate a PC fingerprint based on system info.
    
    This is a placeholder implementation. In production, you would:
    - Use hardware info (MAC address, disk serial, etc.)
    - Hash multiple identifiers
    - Make it difficult to spoof
    
    Returns:
        String identifier for the PC
    """
    # Placeholder: combine platform info
    info = f"{platform.system()}-{platform.release()}-{platform.processor()}"
    return hashlib.sha256(info.encode()).hexdigest()[:16]

