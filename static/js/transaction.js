function filterTable(input, columnIndex) {
    const filter = input.value.toLowerCase();
    const table = document.getElementById("transactionTable");
    const rows = table.getElementsByTagName("tr");

    for (let i = 1; i < rows.length; i++) { // Start at 1 to skip the header row
        const cell = rows[i].getElementsByTagName("td")[columnIndex];
        if (cell) {
            const cellText = cell.textContent || cell.innerText;
            rows[i].style.display = cellText.toLowerCase().includes(filter) ? "" : "none";
        }
    }
}