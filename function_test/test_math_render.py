import urllib.request
import urllib.parse
import os

def render_latex_to_image(latex_str, output_path):
    # urlencode the latex string to be safe in URL
    encoded_eq = urllib.parse.quote(latex_str)
    
    # codecogs URL requires query string to just be the equation, or with preceding arguments
    # Let's try codecogs: https://latex.codecogs.com/png.image?\dpi{300}\bg{white}%20{equation_encoded}
    url = f"https://latex.codecogs.com/png.image?\\dpi{{300}}\\bg{{white}}%20{encoded_eq}"
    
    print(f"Requesting: {url}")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            with open(output_path, 'wb') as f:
                f.write(response.read())
        print(f"Success! Saved to {output_path}")
        return True
    except Exception as e:
        print(f"Failed to render LaTeX: {e}")
        return False

if __name__ == "__main__":
    os.makedirs("temp", exist_ok=True)
    tests = [
        "E=mc^2",
        "\\int_{0}^{\\infty} x^2 dx",
        "\\mathbb{E}[\\sum_{t} \\gamma^t r_t]"
    ]
    for i, eq in enumerate(tests):
        render_latex_to_image(eq, f"temp/test_eq_{i}.png")
