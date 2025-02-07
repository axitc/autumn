async function exchangeData () {
	/* get first [tab] from list of current active tab (which is just one) */
	const [tab] = await chrome.tabs.query({active: true, currentWindow: true});

	/* extract tab's title and text */
	chrome.scripting.executeScript(
		{
			target: {tabId: tab.id},
			func: () => ({
				title: document.title,
				text: document.body.innerText
			}),
		},

		/* catch above anon func's results and execute following anon func */
		async (results) => {
			/* sanity check */
			if (results && results[0] && results[0].result) {
				const {title, text} = results[0].result;

				/* sent title and text to server */
				try {
					const response = await fetch("http://localhost:8000/autumn",
						{
							method: "POST",
							headers: {
								"Content-Type": "application/json"
							},
							body: JSON.stringify({
								url: tab.url,
								title: title.trim(),
								text: text.trim(),
							})
						}
					);

					if (response.ok) {
						const data = await response.json();
						/* title fetched for sake of interface consistency */
						document.getElementById("title").innerText = `${data.title}`;
						document.getElementById("tag").innerHTML = `<strong>Tag : </strong>${data.tag}`;
						document.getElementById("summary").innerText = `${data.summary}`;
						document.getElementById("toplinks").innerHTML = `<strong>Similar links :</strong>${data.toplinks}`;
					} else {
						document.getElementById("title").innerText = "(Internal Server Error)";
					}
				} catch (error) {
					console.error(error);
					document.getElementById("title").innerText = "(Server Unavailable)";
				}
			} else {
				document.getElementById("title").innerText = "(Text Extraction Failed)";
			}
		}
	);
}

/* run on popup load */
document.addEventListener("DOMContentLoaded", exchangeData);
