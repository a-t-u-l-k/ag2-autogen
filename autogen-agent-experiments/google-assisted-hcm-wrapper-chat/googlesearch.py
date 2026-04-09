import requests

def google_search(query, api_key, cse_id, **kwargs):
    service_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': query,
        'key': api_key,
        'cx': cse_id,
        **kwargs
    }
    response = requests.get(service_url, params=params)
    response.raise_for_status()  # Raise an error for bad status codes
    search_results = response.json()
    
    # Extract and format the results
    results = []
    if 'items' in search_results:
        for item in search_results['items']:
            results.append({
                'title': item.get('title', ''),
                'link': item.get('link', ''),
                'snippet': item.get('snippet', '')
            })
    
    return results

# Example usage
api_key = '<set-google-api-key>'
cse_id = '<set-google-cse-id>'
query = 'stock price of ORCL'

results = google_search(query, api_key, cse_id)
for result in results:
    print(f"Title: {result['title']}\nLink: {result['link']}\nSnippet: {result['snippet']}\n")

