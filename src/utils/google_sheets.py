#!/usr/bin/env python3
"""
Author: Fernando Corrales <fscpython@gmail.com>
Purpose: Upload DataFrame to Google Sheets
Source:
    - https://towardsdatascience.com/using-python-to-push-your-pandas-dataframe-to-google-sheets-de69422508f
    - https://medium.com/@jb.ranchana/write-and-append-dataframes-to-google-sheets-in-python-f62479460cf0
    - https://medium.com/@vince.shields913/reading-google-sheets-into-a-pandas-dataframe-with-gspread-and-oauth2-375b932be7bf
"""

__all__ = ["GoogleSheets", "get_google_sheets"]


import argparse
import json
from dataclasses import dataclass, field
from typing import Optional

import gspread  # https://docs.gspread.org/en/latest/index.html#
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

from ..config import settings

# Filas enviadas por request a la API de Google Sheets (payloads acotados)
UPLOAD_CHUNK_ROWS: int = 5000

# from google.oauth2.service_account import Credentials


# --------------------------------------------------
@dataclass
class GoogleSheets:
    """Upload DataFrame to Google Sheets
    :param path_credentials_file: json file download from Google
    """

    # path_credentials_file:str
    # credentials: ServiceAccountCredentials = field(
    #     default=None, init=False, repr=False
    # )
    path_credentials_file: Optional[str] = None
    credentials: Credentials = field(default=None, init=False, repr=False)
    gc: gspread.Client = field(default=None, init=False, repr=False)

    # --------------------------------------------------
    def __post_init__(self):
        self.authorize_access()

    # --------------------------------------------------
    def authorize_access(self):
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]

        credentials_json = settings.GOOGLE_CREDENTIALS
        if credentials_json:
            try:
                credentials_dict = json.loads(credentials_json)
                self.credentials = Credentials.from_service_account_info(
                    credentials_dict, scopes=scopes
                )
            except Exception as e:
                raise ValueError("Invalid GOOGLE_CREDENTIALS format") from e
        elif self.path_credentials_file:
            self.credentials = Credentials.from_service_account_file(
                self.path_credentials_file, scopes=scopes
            )
        else:
            raise ValueError("No valid credentials provided")
        # self.credentials = ServiceAccountCredentials.from_json_keyfile_name(
        #     self.path_credentials_file, scope
        # )
        self.gc = gspread.authorize(self.credentials)

    # --------------------------------------------------
    def to_google_sheets(
        self, df: pd.DataFrame, spreadsheet_key: str, wks_name: str = "Hoja 1"
    ) -> None:
        """Method to upload DataFrame to Google Sheets
        :param df: pandas DataFrame to upload
        :param spreadsheet_key: can be found in the URL of a
        previously created sheet
        :param wks_name: Worksheet name
        """
        try:
            sheet = self.gc.open_by_key(spreadsheet_key)
            try:
                worksheet = sheet.worksheet(wks_name)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = sheet.add_worksheet(
                    title=wks_name,
                    rows=str(max(len(df) + 1, 100)),
                    cols=str(max(len(df.columns), 20)),
                )
            if df.empty:
                delete_range = f"{wks_name}!A2:ZZ100000"
                sheet.values_clear(delete_range)
                print(f"❌ Data deleted from '{wks_name}' because DF was empty")
            else:
                worksheet.clear()
                # Subida por lotes: payloads acotados evitan timeouts/413
                # desde instancias con poca CPU/RAM (ej: capa gratuita de Koyeb)
                self._update_in_chunks(worksheet, df, UPLOAD_CHUNK_ROWS)
                print(
                    f"✅ Data uploaded successfully to '{wks_name}' "
                    f"({len(df)} rows)"
                )
        except Exception as e:
            print(f"❌ Error uploading data: {e}")
            raise

    # --------------------------------------------------
    def _update_in_chunks(
        self, worksheet: gspread.Worksheet, df: pd.DataFrame, chunk_rows: int
    ) -> None:
        """Escribe el DataFrame en el worksheet en bloques de `chunk_rows` filas.

        El encabezado viaja junto al primer bloque; cada bloque posterior usa
        un rango A1 explícito para ubicarse a continuación (gspread le agrega
        el prefijo del nombre de la hoja automáticamente).
        """
        last_col: str = rowcol_to_a1(1, len(df.columns))[:-1]
        total_rows: int = len(df)
        offset: int = 0
        is_first: bool = True

        while is_first or offset < total_rows:
            rows: list[list] = df.iloc[offset : offset + chunk_rows].values.tolist()
            if is_first:
                rows = [df.columns.values.tolist()] + rows
                start_row: int = 1
                is_first = False
            else:
                # +1 por el encabezado, +1 por ser 1-based
                start_row = offset + 2
            end_row: int = start_row + len(rows) - 1
            worksheet.update(rows, f"A{start_row}:{last_col}{end_row}")
            offset += chunk_rows

    # https://github.com/maybelinot/df2gspread/issues/41#issuecomment-1154527949

    # def upload_pandas_df(self, df:pd.DataFrame):
    #   values = [df.columns.values.tolist()]
    #   values.extend(df.values.tolist())
    #   sheet.values_update(
    #     self.title,
    #     params = { 'valueInputOption': 'USER_ENTERED' },
    #     body = { 'values': values }
    #   )

    # gspread.Worksheet.upload_pandas_df = upload_pandas_df


# --------------------------------------------------
_shared_client: Optional[GoogleSheets] = None


# --------------------------------------------------
def get_google_sheets() -> GoogleSheets:
    """Devuelve una instancia cacheada de GoogleSheets.

    Reutiliza la autorización OAuth entre llamadas para evitar
    re-autorizar en cada exportación.
    """
    global _shared_client
    if _shared_client is None:
        _shared_client = GoogleSheets()
    return _shared_client


# --------------------------------------------------
def get_args():
    """Get needed params from user input"""
    parser = argparse.ArgumentParser(
        description="Upload DataFrame to Google Sheets",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "spreadsheet_key",
        metavar="spreadsheet_key",
        type=str,
        help="can be found in the URL of a previously created sheet",
    )

    parser.add_argument(
        "-c",
        "--credentials",
        metavar="json_credentials",
        type=str,
        help="Google's json file credentials name. Must be in the same folder",
        default=None,
    )

    parser.add_argument(
        "-w",
        "--wks_name",
        metavar="worksheet_name",
        default="Hoja 1",
        type=str,
        help="worksheet_name",
    )

    return parser.parse_args()


# --------------------------------------------------
def main():
    """Let's try it"""
    d = {"col1": [1, 2], "col2": [3, 4]}
    df = pd.DataFrame(data=d)

    args = get_args()

    gs = GoogleSheets(args.credentials)
    gs.to_google_sheets(
        df, spreadsheet_key=args.spreadsheet_key, wks_name=args.wks_name
    )
    print("Upload complete")


# --------------------------------------------------
if __name__ == "__main__":
    main()
