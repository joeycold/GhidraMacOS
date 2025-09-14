import os
import shutil
import subprocess
import urllib.request
import zipfile
import tarfile
import hashlib
import json
from colorama import Fore, Style, init
from tqdm import tqdm

# Initialize colorama
init(autoreset=True)

def print_banner():
    banner = f"""
{Fore.MAGENTA}
  _____                _____ _
 / ____|              / ____| |
| (___  _ __ ___  ___| (___ | | ___
 \\___ \\| '__/ _ \\/ _ \\\\___ \\| |/ _ \\
 ____) | | |  __/  __/____) | |  __/
|_____/|_|  \\___|\\___|_____/|_|\\___|

{Fore.CYAN}
    .-.     .-.     .-.     .-.     .-.     .-.     .-.     .-.     .-.
   (_  )   (_  )   (_  )   (_  )   (_  )   (_  )   (_  )   (_  )   (_  )
     /       /       /       /       /       /       /       /       /
    (       (       (       (       (       (       (       (       (
     `-'     `-'     `-'     `-'     `-'     `-'     `-'     `-'     `-'
{Style.RESET_ALL}
"""
    print(banner)

# URLs and expected checksums
java_url = "https://download.java.net/java/GA/jdk21.0.2/f2283984656d49d69e91c558476027ac/13/GPL/openjdk-21.0.2_macos-aarch64_bin.tar.gz"
java_expected_sha256 = "b3d588e16ec1e0ef9805d8a696591bd518a5cea62567da8f53b5ce32d11d22e4"  # JDK checksum not available, will skip verification
ghidra_url = "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_11.4.2_build/ghidra_11.4.2_PUBLIC_20250826.zip"
ghidra_expected_sha256 = "795a02076af16257bd6f3f4736c4fc152ce9ff1f95df35cd47e2adc086e037a6"  # From Homebrew Cask JSON

# Paths
cwd = os.getcwd()
temp_dir = os.path.join(cwd, "ghidra_install")
applet_path = os.path.join(temp_dir, "Ghidra-OSX-Launcher-Script.scpt")
app_dir = os.path.join(temp_dir, "Ghidra.app")
jdk_dir = os.path.join(temp_dir, "jdk")
ghidra_dir = os.path.join(temp_dir, "ghidra")
applications_dir = "/Applications"

# Names
launch_script_path = os.path.join(temp_dir,'Ghidra.app/Contents/Resources/ghidra/support/launch.sh')
ghidra_run_path = os.path.join(temp_dir, 'Ghidra.app/Contents/Resources/ghidra/ghidraRun')


# Create temporary directory
os.makedirs(temp_dir, exist_ok=True)


def calculate_sha256(file_path):
    """Calculate SHA-256 checksum of a file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"{Fore.RED}Error calculating checksum for {file_path}: {e}{Style.RESET_ALL}")
        raise

def verify_checksum(file_path, expected_sha256, file_name):
    """Verify file checksum against expected value"""
    try:
        print(f"{Fore.YELLOW}Verifying {file_name} checksum...{Style.RESET_ALL}")
        actual_sha256 = calculate_sha256(file_path)
        if actual_sha256 == expected_sha256:
            print(f"{Fore.GREEN}{file_name} checksum verification passed{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}{file_name} checksum verification failed!{Style.RESET_ALL}")
            print(f"{Fore.RED}Expected: {expected_sha256}{Style.RESET_ALL}")
            print(f"{Fore.RED}Actual:   {actual_sha256}{Style.RESET_ALL}")
            return False
    except Exception as e:
        print(f"{Fore.RED}Error verifying checksum for {file_name}: {e}{Style.RESET_ALL}")
        return False

def build_native_binaries(ghidra_dir, jdk_home):
    """Build native binaries using Gradle"""
    try:
        gradle_dir = os.path.join(ghidra_dir, "support", "gradle")
        if not os.path.exists(gradle_dir):
            print(f"{Fore.RED}Gradle directory not found: {gradle_dir}{Style.RESET_ALL}")
            return False
        
        print(f"{Fore.YELLOW}Building native binaries with Gradle...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Using JDK: {jdk_home}{Style.RESET_ALL}")
        
        # Ensure gradlew has execute permissions
        gradlew_path = os.path.join(gradle_dir, "gradlew")
        if os.path.exists(gradlew_path):
            add_execute_permissions(gradlew_path)
        
        # Set up environment variables
        env = os.environ.copy()
        env['JAVA_HOME'] = jdk_home
        env['PATH'] = f"{os.path.join(jdk_home, 'bin')}:{env.get('PATH', '')}"
        
        # Change to gradle directory and run buildNatives
        result = subprocess.run(
            ["./gradlew", "buildNatives"],
            cwd=gradle_dir,
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"{Fore.GREEN}Native binaries built successfully!{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}Gradle build failed with return code {result.returncode}{Style.RESET_ALL}")
            print(f"{Fore.RED}STDOUT: {result.stdout}{Style.RESET_ALL}")
            print(f"{Fore.RED}STDERR: {result.stderr}{Style.RESET_ALL}")
            return False
            
    except Exception as e:
        print(f"{Fore.RED}Error building native binaries: {e}{Style.RESET_ALL}")
        return False

def add_execute_permissions(file_path):
    try:
        subprocess.run(["chmod", "+x", file_path], check=True)
        print(f"{Fore.GREEN}Added execute permissions to {file_path}{Style.RESET_ALL}")
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error adding execute permissions to {file_path}: {e}{Style.RESET_ALL}")
        raise

def download_file(url, dest, expected_sha256=None, file_name=None):
    if os.path.exists(dest):
        print(f"{Fore.YELLOW}{dest} already exists, skipping download{Style.RESET_ALL}")
        # Verify existing file if checksum is provided
        if expected_sha256 and file_name:
            if not verify_checksum(dest, expected_sha256, file_name):
                print(f"{Fore.YELLOW}Existing file failed checksum verification, re-downloading...{Style.RESET_ALL}")
                os.remove(dest)
            else:
                return
    try:
        print(f"{Fore.YELLOW}Downloading {url} to {dest}{Style.RESET_ALL}")

        with tqdm(unit='B', unit_scale=True, miniters=1, desc=url.split('/')[-1]) as t:
            def reporthook(blocknum, blocksize, totalsize):
                t.total = totalsize
                t.update(blocknum * blocksize - t.n)

            urllib.request.urlretrieve(url, dest, reporthook)
        
        # Verify downloaded file if checksum is provided
        if expected_sha256 and file_name:
            if not verify_checksum(dest, expected_sha256, file_name):
                raise Exception(f"Downloaded {file_name} failed checksum verification")
    except Exception as e:
        print(f"{Fore.RED}Error downloading {url}: {e}{Style.RESET_ALL}")
        raise

def extract_zip(file_path, dest_dir):
    try:
        print(f"{Fore.YELLOW}Extracting {file_path} to {dest_dir}{Style.RESET_ALL}")
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
    except Exception as e:
        print(f"{Fore.RED}Error extracting {file_path}: {e}{Style.RESET_ALL}")
        raise

def extract_tar_gz(file_path, dest_dir):
    try:
        print(f"{Fore.YELLOW}Extracting {file_path} to {dest_dir}{Style.RESET_ALL}")
        with tarfile.open(file_path, 'r:gz') as tar_ref:
            tar_ref.extractall(dest_dir, filter='data')
    except Exception as e:
        print(f"{Fore.RED}Error extracting {file_path}: {e}{Style.RESET_ALL}")
        raise

def main():
    try:
        # Create Ghidra.app as an empty directory first.
        subprocess.run(["osacompile", "-o", app_dir, applet_path], check=True)
        print(f"{Fore.GREEN}Created Ghidra.app at {app_dir}{Style.RESET_ALL}")

        # Step 2: Download and extract the latest OpenJDK
        jdk_tar_path = os.path.join(temp_dir, "openjdk.tar.gz")
        download_file(java_url, jdk_tar_path, java_expected_sha256, "OpenJDK")
        # Clean the jdk directory before extraction to avoid permission issues
        if os.path.exists(jdk_dir):
            shutil.rmtree(jdk_dir)
        os.makedirs(jdk_dir, exist_ok=True)
        extract_tar_gz(jdk_tar_path, jdk_dir)
        jdk_extracted_dir = os.path.join(jdk_dir, os.listdir(jdk_dir)[0])
        # Place JDK in the correct location within the app bundle
        jdk_final_app_dir = os.path.join(app_dir, "Contents", "Resources", "jdk")
        # Remove existing jdk directory if it exists
        if os.path.exists(jdk_final_app_dir):
            shutil.rmtree(jdk_final_app_dir)
        shutil.copytree(jdk_extracted_dir, jdk_final_app_dir)

    except Exception as e:
        print(f"{Fore.RED}Installation failed: {e}{Style.RESET_ALL}")
        exit()

    try:
        # Step 3: Download and extract the latest Ghidra
        ghidra_zip_path = os.path.join(temp_dir, "ghidra.zip")
        download_file(ghidra_url, ghidra_zip_path, ghidra_expected_sha256, "Ghidra")
        # Clean the ghidra directory before extraction to avoid permission issues
        if os.path.exists(ghidra_dir):
            shutil.rmtree(ghidra_dir)
        os.makedirs(ghidra_dir, exist_ok=True)
        extract_zip(ghidra_zip_path, ghidra_dir)
        ghidra_extracted_dir = os.path.join(ghidra_dir, os.listdir(ghidra_dir)[0])
        # Place Ghidra in the correct location within the app bundle
        ghidra_final_app_dir = os.path.join(app_dir, "Contents", "Resources", "ghidra")
        # Remove existing ghidra directory if it exists
        if os.path.exists(ghidra_final_app_dir):
            shutil.rmtree(ghidra_final_app_dir)
        shutil.copytree(ghidra_extracted_dir, ghidra_final_app_dir)

        # Step 4: Build native binaries using Gradle
        jdk_home = os.path.join(app_dir, "Contents", "Resources", "jdk", "Contents", "Home")
        if not build_native_binaries(ghidra_final_app_dir, jdk_home):
            print(f"{Fore.YELLOW}Warning: Native binary build failed, but continuing with installation...{Style.RESET_ALL}")

        # Step 5: Add execute permissions to the Ghidra launcher script
        add_execute_permissions(launch_script_path)
        add_execute_permissions(ghidra_run_path)

        print(f"{Fore.GREEN}Ghidra installation completed successfully!{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}Installation failed: {e}{Style.RESET_ALL}")
        exit()

if __name__ == "__main__":
    print_banner()
    main()
