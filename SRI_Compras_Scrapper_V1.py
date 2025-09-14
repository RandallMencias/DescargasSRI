import time
import os
import shutil
import re
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class SRIDownloader:
    def __init__(self):
        # Setup directories
        self.base_dir = Path.home() / "Downloads" / "sri_files"
        self.pdf_dir = self.base_dir / "pdf"
        self.xml_dir = self.base_dir / "xml"
        self.temp_dir = Path.home() / "Downloads"  # Chrome's default download location

        # Create directories
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.xml_dir.mkdir(parents=True, exist_ok=True)

        self.driver = None
        self.wait = None

    def setup_driver(self):
        """Setup Chrome driver with download preferences"""
        chrome_options = Options()

        # Download preferences - downloads go to default Downloads folder first
        prefs = {
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "safebrowsing.disable_download_protection": True,
            "plugins.always_open_pdf_externally": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument("--safebrowsing-disable-download-protection")

        try:
            service = Service()  # Uses system PATH for chromedriver
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            print("✅ Chrome driver setup successful")
        except Exception as e:
            print(f"❌ Error setting up Chrome driver: {e}")
            raise

    def wait_for_download_complete(self, timeout=15):
        """Wait for any downloads to complete"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check for .crdownload files (Chrome's temporary download files)
            downloading = list(self.temp_dir.glob("*.crdownload"))
            if not downloading:
                time.sleep(0.015)  # Small buffer to ensure file is fully written
                return True
            time.sleep(0.25)
        return False

    def move_downloaded_files(self, factura_number):
        """Move downloaded files from temp directory to organized folders"""
        try:
            # Look for recently downloaded files (last 20 seconds)
            recent_files = []
            now = time.time()

            for file_path in self.temp_dir.iterdir():
                if file_path.is_file() and (now - file_path.stat().st_mtime) < 20:
                    if file_path.suffix.lower() in ['.pdf', '.xml']:
                        recent_files.append(file_path)

            moved_files = []
            for file_path in recent_files:
                # Determine destination based on file extension
                if file_path.suffix.lower() == '.pdf':
                    dest_dir = self.pdf_dir
                    file_type = "PDF"
                elif file_path.suffix.lower() == '.xml':
                    dest_dir = self.xml_dir
                    file_type = "XML"
                else:
                    continue

                # Use factura number as filename
                clean_name = "".join(c for c in factura_number if c.isalnum() or c in ('-', '_', ' ')).strip()
                # Insert space between 'Facturas' and 'Number' if needed
                clean_name = re.sub(r'(Facturas)(Number)', r'\1 \2', clean_name)
                if not clean_name:
                    clean_name = f"documento_{int(time.time())}"

                dest_path = dest_dir / f"{clean_name}{file_path.suffix.lower()}"

                # Handle duplicate filenames
                counter = 1
                original_dest = dest_path
                while dest_path.exists():
                    dest_path = original_dest.with_stem(f"{original_dest.stem}_{counter}")
                    counter += 1

                # Move file
                shutil.move(str(file_path), str(dest_path))
                moved_files.append((file_type, dest_path))
                print(f"  📁 {file_type} saved as: {dest_path.name}")

            return moved_files

        except Exception as e:
            print(f"  ⚠️ Error organizing files: {e}")
            return []

    def download_document_by_index(self, index):
        """Download both XML and PDF for a document by its index"""

        try:
            # Construct the specific link IDs for this row
            xml_link_id = f"frmPrincipal:tablaCompRecibidos:{index}:lnkXml"
            pdf_link_id = f"frmPrincipal:tablaCompRecibidos:{index}:lnkPdf"

            # Get the invoice number from column 3 (index 2)
            factura_number = f"documento_{index}"
            try:
                # Find the XML link first to get its row
                xml_link = self.driver.find_element(By.ID, xml_link_id)
                row = xml_link.find_element(By.XPATH, "./ancestor::tr")
                cells = row.find_elements(By.TAG_NAME, "td")

                # Get invoice number from column 3 (index 2)
                if len(cells) >= 3:
                    factura_cell = cells[2]
                    factura_text = factura_cell.text.strip()
                    if factura_text and len(factura_text) > 0:
                        factura_number = factura_text

            except Exception as e:
                print(f"  🔍 Could not extract invoice number: {e}")

            print(f"📄 Document {index + 1}: {factura_number}")

            downloads_successful = []

            # Download XML
            try:
                xml_link = self.driver.find_element(By.ID, xml_link_id)
                if xml_link.is_displayed() and xml_link.is_enabled():
                    self.driver.execute_script("arguments[0].click();", xml_link)
                    if self.wait_for_download_complete():
                        downloads_successful.append("XML")
                        print(f"  ✅ XML")
                    else:
                        print(f"  ⚠️ XML timeout")
                else:
                    print(f"  ⚠️ XML not available")
            except NoSuchElementException:
                print(f"  ⚠️ XML link not found")
            except Exception as e:
                print(f"  ⚠️ XML error: {e}")

            # Small delay between downloads
            time.sleep(0.5)
            # if index == 0:
            #     input(f"Have you accepted the download multiple files prompt? Press Enter to continue...{index}")
            # Download PDF
            try:
                pdf_link = self.driver.find_element(By.ID, pdf_link_id)
                if pdf_link.is_displayed() and pdf_link.is_enabled():
                    self.driver.execute_script("arguments[0].click();", pdf_link)
                    if self.wait_for_download_complete():
                        downloads_successful.append("PDF")
                        print(f"  ✅ PDF")
                    else:
                        print(f"  ⚠️ PDF timeout")
                else:
                    print(f"  ⚠️ PDF not available")
            except NoSuchElementException:
                print(f"  ⚠️ PDF link not found")
            except Exception as e:
                print(f"  ⚠️ PDF error: {e}")

            if index == 0:
                input(f"Have you accepted the download multiple files prompt? Press Enter to continue...{index}")

            # Move downloaded files to organized folders
            if downloads_successful:
                time.sleep(0.5)  # Allow downloads to complete
                moved_files = self.move_downloaded_files(factura_number)
                return len(moved_files) > 0

            return False

        except Exception as e:
            print(f"  ❌ Error processing document {index + 1}: {e}")
            return False

    def download_current_page(self):
        """Download all documents from the current page"""
        try:
            # Wait for the table with specific ID pattern to load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[id*='tablaCompRecibidos'][id*='lnkXml']")))

            # Find all XML links and extract their actual indices
            xml_links = self.driver.find_elements(By.CSS_SELECTOR, "a[id*='tablaCompRecibidos'][id*='lnkXml']")

            # Extract the actual row indices from the link IDs
            document_indices = []
            for xml_link in xml_links:
                link_id = xml_link.get_attribute('id')  # e.g., "frmPrincipal:tablaCompRecibidos:50:lnkXml"
                try:
                    # Extract the index number from the ID
                    parts = link_id.split(':')
                    if len(parts) >= 3 and parts[2].isdigit():
                        index = int(parts[2])
                        document_indices.append(index)
                except:
                    continue

            num_documents = len(document_indices)
            print(f"\n📊 Found {num_documents} documents on this page (indices: {document_indices})")

            if num_documents == 0:
                print("⚠️ No document download links found")
                return False

            successful = 0
            for i, doc_index in enumerate(document_indices):
                if self.download_document_by_index(doc_index):
                    successful += 1
                time.sleep(0.2)  # Small delay between downloads

            print(f"\n✅ Page complete: {successful}/{num_documents} documents processed successfully")
            return successful > 0

        except TimeoutException:
            print("❌ Timeout waiting for page to load")
            return False
        except Exception as e:
            print(f"❌ Error downloading page: {e}")
            return False

    def go_to_next_page(self):
        """Navigate to the next page"""
        try:
            # Look for the next button - it should NOT have 'ui-state-disabled' class
            next_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".ui-paginator-next")

            for next_button in next_buttons:
                classes = next_button.get_attribute("class") or ""
                if "ui-state-disabled" not in classes:
                    # This next button is enabled
                    self.driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(2)  # Wait for page to load
                    print("✅ Navigated to next page")
                    return True

            print("⚠️ Next page button is disabled - no more pages")
            return False

        except Exception as e:
            print(f"❌ Error navigating to next page: {e}")
            return False

    def run(self, start_url):
        """Main execution method"""
        try:
            print("🚀 Starting SRI Document Downloader")
            print(f"📁 PDF files will be saved to: {self.pdf_dir}")
            print(f"📁 XML files will be saved to: {self.xml_dir}")

            self.setup_driver()

            print(f"\n🌐 Navigating to SRI portal...")
            self.driver.get(start_url)

            print("\n🔑 Please login manually and navigate to the documents page.")
            print("   Make sure the table with documents is visible.")
            input("   Press Enter when ready to start downloading...")

            page_count = 0
            total_success = 0

            while True:
                page_count += 1
                print(f"\n{'=' * 50}")
                print(f"📄 Processing Page {page_count}")
                print('=' * 50)

                if self.download_current_page():
                    total_success += 1
                else:
                    print("⚠️ No successful downloads on this page")

                # Ask user what to do next
                print(f"\nOptions:")
                print("  [y] Go to next page")
                print("  [n] Stop downloading")
                print("  [r] Retry current page")

                choice = input("Choose option (y/n/r): ").lower().strip()

                if choice == 'n':
                    break
                elif choice == 'r':
                    continue
                elif choice == 'y':
                    if not self.go_to_next_page():
                        print("📄 No more pages available or error navigating")
                        break
                else:
                    print("Invalid choice, stopping...")
                    break

            print(f"\n{'=' * 50}")
            print("📊 DOWNLOAD SUMMARY")
            print('=' * 50)
            print(f"📄 Pages processed: {page_count}")
            print(f"📁 PDF files location: {self.pdf_dir}")
            print(f"📁 XML files location: {self.xml_dir}")
            print("✅ Download session completed!")

        except KeyboardInterrupt:
            print("\n⚠️ Download interrupted by user")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
        finally:
            if self.driver:
                print("\nClosing browser...")
                self.driver.quit()


# Main execution
if __name__ == "__main__":
    START_URL = "https://srienlinea.sri.gob.ec/comprobantes-electronicos-internet/pages/consultas/recibidos/comprobantesRecibidos.jsf?&contextoMPT=https://srienlinea.sri.gob.ec/tuportal-internet&pathMPT=Facturaci%F3n%20Electr%F3nica&actualMPT=Comprobantes%20electr%F3nicos%20recibidos%20&linkMPT=%2Fcomprobantes-electronicos-internet%2Fpages%2Fconsultas%2Frecibidos%2FcomprobantesRecibidos.jsf%3F&esFavorito=S"

    downloader = SRIDownloader()
    downloader.run(START_URL)