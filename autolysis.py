# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "pandas",
#   "seaborn",
#   "matplotlib",
#   "httpx",
#   "openai",
# ]
# ///

import os  # Helps with operating system interactions like file paths
import sys  # Provides system-specific parameters and functions
import logging  # For creating log messages and tracking script execution
import pandas as pd  # Data manipulation and analysis library
import seaborn as sns  # Statistical data visualization
import matplotlib.pyplot as plt  # Plotting library
import httpx  # HTTP client for making API requests
import traceback  # Helps in printing detailed error information
import json  # Allows working with JSON data
from typing import List, Dict  # Helps with type hinting
from shutil import move  # Used for moving files

# Sets up logging to track script activities and errors
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
class AutomatedAnalysis:
    def __init__(self, dataset_path: str):
        """Initialize the analysis with the dataset."""
        self.dataset_path = dataset_path
        self.aiproxy_token = os.getenv("AIPROXY_TOKEN")

        if not self.aiproxy_token:
            raise ValueError("AIPROXY_TOKEN environment variable is not set.")

        self.df = self._load_dataset()

    def _load_dataset(self) -> pd.DataFrame:
        """Load the dataset with fallback for multiple encodings."""
        encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252", "utf-16"]

        for encoding in encodings:
            try:
                logger.info(f"Trying encoding: {encoding}")
                return pd.read_csv(self.dataset_path, encoding=encoding)
            except Exception as e:
                logger.warning(f"Failed with encoding {encoding}: {e}")

        raise ValueError(f"Could not read the CSV file with any encoding.")

    def analyze(self) -> Dict:
        """Perform generic analysis of the dataset."""
        analysis = {
            "shape": self.df.shape,
            "columns": list(self.df.columns),
            "missing_values": self.df.isnull().sum().to_dict(),
            "summary_statistics": self.df.describe(include='all').to_dict(),
        }

        numeric_cols = self.df.select_dtypes(include=['number']).columns
        if not numeric_cols.empty:
            analysis["correlation_matrix"] = self.df[numeric_cols].corr().to_dict()

        return analysis

    def visualize(self, output_dir: str) -> List[str]:
        """Generate visualizations and save them as PNG files."""
        visualizations = []

        # Visualization 1: Missing values
        missing_values = self.df.isnull().sum()
        if missing_values.any():
            plt.figure(figsize=(10, 6))
            missing_values[missing_values > 0].plot(kind="bar")
            plt.title("Missing Values by Column")
            plt.ylabel("Count")
            plt.tight_layout()
            path = os.path.join(output_dir, "missing_values.png")
            plt.savefig(path)
            visualizations.append(path)
            plt.close()

        # Visualization 2: Correlation heatmap
        numeric_cols = self.df.select_dtypes(include=['number'])
        if not numeric_cols.empty:
            plt.figure(figsize=(10, 8))
            sns.heatmap(numeric_cols.corr(), annot=True, cmap="coolwarm")
            plt.title("Correlation Heatmap")
            plt.tight_layout()
            path = os.path.join(output_dir, "correlation_heatmap.png")
            plt.savefig(path)
            visualizations.append(path)
            plt.close()

        return visualizations

    def generate_narrative(self, analysis: Dict) -> str:
        """Generate a narrative summary using the LLM."""
        prompt = f"""
        Write a narrative for the dataset analysis:

        Shape: {analysis['shape']}
        Columns: {', '.join(analysis['columns'])}
        Missing Values: {json.dumps(analysis['missing_values'], indent=2)}
        Summary Statistics: {json.dumps(analysis['summary_statistics'], indent=2)}
        Correlation Matrix: {json.dumps(analysis.get('correlation_matrix', {}), indent=2)}

        Provide key insights and recommendations in Markdown format.
        """

        try:
            headers = {
                "Authorization": f"Bearer {self.aiproxy_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}]
            }

            response = httpx.post(
                "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return "Error: Unable to generate narrative. Please review the dataset manually."

    def save_output(self, output_dir: str, narrative: str, visualizations: List[str]):
        """Save narrative and visualizations."""
        os.makedirs(output_dir, exist_ok=True)

        # Save README
        readme_path = os.path.join(output_dir, "README.md")
        with open(readme_path, "w") as f:
            f.write(f"# Analysis of {os.path.basename(self.dataset_path)}\n\n")
            f.write("## Narrative Summary\n\n")
            f.write(narrative + "\n\n")
            f.write("## Visualizations\n\n")
            for vis in visualizations:
                f.write(f"![{os.path.basename(vis)}]({os.path.basename(vis)})\n\n")

        # Move PNGs to output directory
        for vis in visualizations:
            move(vis, output_dir)

    def run(self):
        """Execute the analysis workflow."""
        logger.info("Starting analysis...")
        output_dir = os.path.splitext(os.path.basename(self.dataset_path))[0]

        analysis = self.analyze()
        visualizations = self.visualize(output_dir)
        narrative = self.generate_narrative(analysis)
        self.save_output(output_dir, narrative, visualizations)

        logger.info(f"Analysis complete. Results saved in {output_dir}.")


def main():
    if len(sys.argv) != 2:
        print("Usage: uv run autolysis.py <dataset.csv>")
        sys.exit(1)

    dataset_path = sys.argv[1]

    if not os.path.exists(dataset_path):
        print(f"File not found: {dataset_path}")
        sys.exit(1)

    try:
        analyzer = AutomatedAnalysis(dataset_path)
        analyzer.run()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
