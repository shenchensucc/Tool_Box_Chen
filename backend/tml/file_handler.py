"""
FileHandler Module for TML Data Processing

This module handles file operations for the TML Data Processing Tool.
It manages input file reading and Excel file operations with dynamic file paths.

Key Features:
- Manages file paths dynamically for uploaded files
- Handles Excel file reading with error checking
- Provides consistent file naming and organization
- Supports temporary file operations

Dependencies:
- pandas: For Excel file reading
- os: For file path operations
"""

import os
import pandas as pd
from typing import Optional


class FileHandler:
    """
    A class to handle file operations for the TML data processing tool.
    
    This class provides methods for:
    1. Reading Excel files from dynamic paths
    2. Managing file paths for input and output files
    
    Attributes:
        source_path (str): Path to the source data file
        template_path (str): Path to the template file
        output_dir (str): Directory for output files
    """
    
    def __init__(self, source_path: str, template_path: str, output_dir: str):
        """
        Initialize the FileHandler with dynamic file paths.
        
        Args:
            source_path: Path to the source Excel file
            template_path: Path to the template Excel file
            output_dir: Directory where output files will be saved
        
        Note:
            - Creates output directory if it doesn't exist
        """
        self.source_path = source_path
        self.template_path = template_path
        self.output_dir = output_dir
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Define output file paths with numbering according to static data order
        self.output_files = {
            "Status": os.path.join(output_dir, "01_TM_Loader_Status.xlsx"),
            "FollowUp": os.path.join(output_dir, "02_TM_Loader_FollowUp.xlsx"),
            "CodeYearTmin": os.path.join(output_dir, "03_TM_Loader_CodeYearTmin.xlsx"),
            "DesignCode": os.path.join(output_dir, "04_TM_Loader_DC.xlsx"),
            "MaterialSpec": os.path.join(output_dir, "05_TM_Loader_MaterialSpec.xlsx"),
            "MaterialGrade": os.path.join(output_dir, "06_TM_Loader_MaterialGrad.xlsx"),
            "T": os.path.join(output_dir, "07_TM_Loader_T.xlsx"),
            "PF": os.path.join(output_dir, "08_TM_Loader_PF.xlsx"),
            "OD": os.path.join(output_dir, "09_TM_Loader_OD.xlsx"),
            "NPS": os.path.join(output_dir, "10_TM_Loader_NPS.xlsx"),
            "Schedule": os.path.join(output_dir, "11_TM_Loader_Schedule.xlsx"),
            "P": os.path.join(output_dir, "12_TM_Loader_P.xlsx"),
            "TempCoef": os.path.join(output_dir, "13_TM_Loader_TempCoef.xlsx"),
            "Tnom": os.path.join(output_dir, "14_TM_Loader_Tnom.xlsx"),
            "Tmin": os.path.join(output_dir, "15_TM_Loader_Tmin.xlsx"),
            "OAS": os.path.join(output_dir, "16_TM_Loader_OAS.xlsx"),
            "AS": os.path.join(output_dir, "17_TM_Loader_AllowableStress.xlsx"),
            "AS_All": os.path.join(output_dir, "17_TM_Loader_AllowableStress_All.xlsx"),
            "DF": os.path.join(output_dir, "18_TM_Loader_DesignFactor.xlsx"),
            "JF": os.path.join(output_dir, "19_TM_Loader_JointFactor.xlsx"),
            "LF": os.path.join(output_dir, "20_TM_Loader_LocationFatcor.xlsx")
        }

    def read_excel(self, file_type: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
        """
        Read data from an Excel file.
        
        Args:
            file_type: Type of file to read ("source" or "template")
            sheet_name: Name of the sheet to read (optional)
            
        Returns:
            pd.DataFrame: Data read from the Excel file
            
        Raises:
            FileNotFoundError: If the input file doesn't exist
            ValueError: If the file type is invalid
            
        Note:
            - Validates file existence before reading
            - Supports reading specific sheets
            - Handles both source and template files
        """
        if file_type == "source":
            file_path = self.source_path
        elif file_type == "template":
            file_path = self.template_path
        else:
            raise ValueError(f"Invalid file type: {file_type}. Must be 'source' or 'template'")
            
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")
            
        df = pd.read_excel(file_path, sheet_name=sheet_name, dtype={"Equipment ID": str})
        return df

    def save_excel(self, data: pd.DataFrame, file_type: str, sheet_name: str):
        """
        Save DataFrame to Excel file.
        
        Args:
            data: DataFrame to save
            file_type: Type of output file (key from output_files dict)
            sheet_name: Name of the sheet to save
            
        Raises:
            ValueError: If the file type is invalid
        """
        if file_type not in self.output_files:
            raise ValueError(f"Invalid file type: {file_type}")
            
        file_path = self.output_files[file_type]
        data.to_excel(file_path, sheet_name=sheet_name, index=False)
        print(f"Saved data to {sheet_name} in {file_path}")

