from Communication.PLC import PLC
from Communication.PLCConfig import PRT_PLC_IP_ADDRESS

class PRTPLC(PLC):
    """
    Represents the PRT PLC
    """
    def __init__(self):
        super().__init__(PRT_PLC_IP_ADDRESS)
        # Use (transaction_id, barcode) as dedup key — only skip when BOTH match.
        # This prevents skipping a new cart when the PLC reuses transaction IDs.
        self._last_request_key = {1: None, 2: None}
        self.connect()

    def read_sorter_request(self, sorter_num: int):
        data = self.read_tag(f'SORTER_{sorter_num}_REQUEST')
        if data is None:
            return None

        if data['END'] == 1:
            transaction_id = data['TRANSACTION_ID']

            raw_barcode = data['BARCODE']
            # Normalize barcode: sorter 1 scanner sends barcode + \r terminator, but the PLC
            # string buffer retains stale bytes after the \r (e.g., '8\r00' where '8' is the
            # actual scan and '00' is leftover). Split on \r to get only the real data.
            if not isinstance(raw_barcode, str):
                raw_barcode = str(raw_barcode)
            barcode = raw_barcode.split('\r')[0].replace('\x00', '').replace('\n', '').strip()
            # Zero-pad to 4 digits (e.g., '8' -> '0008')
            barcode = barcode.zfill(4) if barcode else raw_barcode

            # Skip duplicate requests — PLC re-sends same (transaction_id, barcode) when
            # the cart hasn't physically moved. Use both to avoid skipping a new cart
            # when the PLC reuses transaction IDs across different carts.
            request_key = (transaction_id, barcode)
            if request_key == self._last_request_key.get(sorter_num):
                # Still clear END so PLC can proceed; we already responded to this request
                self.write_tag(f'SORTER_{sorter_num}_REQUEST.END', 0)
                return None
            self._last_request_key[sorter_num] = request_key

            print(f"SORTER_REQUEST_{sorter_num}: END: 1, barcode: {barcode}, transaction_id: {transaction_id}")
            self.write_tag(f'SORTER_{sorter_num}_REQUEST.END', 0)
            return barcode, transaction_id

    def send_sorter_response(self, sorter_num: int, transaction_id: int, destination: int):
        # Send all response fields in a single CIP message (~10ms instead of ~40ms).
        # The PLC has a tight physical timing window before the cart passes the diverter.
        self.write_tags(
            (f'SORTER_{sorter_num}_RESPONSE.TRANSACTION_ID', transaction_id),
            (f'SORTER_{sorter_num}_RESPONSE.DESTINATION', destination),
            (f'SORTER_{sorter_num}_RESPONSE.END', 1)
        )
        print(f"SORTER_{sorter_num}_RESPONSE: TRANS_ID: {transaction_id}, DEST: {destination}")

    def read_sorter_report(self, sorter_num: int):
        data = self.read_tag(f'SORTER_{sorter_num}_REPORT')
        if data is None:
            return None
        if data['END'] == 1:
            #Reset to 0
            self.write_tag(f'SORTER_{sorter_num}_REPORT.END', 0)
            raw_barcode = data.get('BARCODE', '')
            # Normalize barcode: strip null chars and whitespace (PLC often uses fixed-length fields filled with \x00)
            if isinstance(raw_barcode, str):
                barcode = raw_barcode.strip('\x00').strip()
            else:
                barcode = str(raw_barcode).strip('\x00').strip()

            # Only log and return when the scanner actually read a barcode (non-empty after normalization)

            if barcode:
                print(f"Sorted_Report: {data}")
                return barcode, data['FLAGS']['ACTIVE'], data['FLAGS']['LOST'], data['FLAGS']['GOOD'], data['FLAGS']['DIVERTED']

            # Treat null/empty barcode as no report
            return None

    def send_watchdog_signal(self):
        self.write_tag('OPC_WATCHDOG', 1)
