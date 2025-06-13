let selectedCustomerId = null;
let selectedWeek = null;

document.addEventListener('DOMContentLoaded', function () {
    const searchBar = document.getElementById('searchBar');
    const confirmBtn = document.getElementById('confirmBtn');

    if (searchBar) {
        searchBar.addEventListener('input', function () {
            const q = this.value.trim();
            if (q.length > 1) fetchResults(q);
        });
    }

    if (confirmBtn) {
        confirmBtn.addEventListener('click', function () {
            markInstallmentPaid(selectedCustomerId, selectedWeek);
            const modal = bootstrap.Modal.getInstance(document.getElementById('confirmModal'));
            modal.hide();
        });
    }
});

function fetchResults(query) {
    fetch(`/search?q=${query}`)
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('collectionContainer');
            container.innerHTML = '';

            if (data.results.length === 0) {
                container.innerHTML = '<p>No results found.</p>';
                return;
            }

            data.results.forEach(customer => {
                let html = `
                    <div class="card mb-3">
                        <div class="card-header bg-light">
                            <strong>${customer.name}</strong> - ${customer.phone}
                        </div>
                        <div class="card-body">
                            <table class="table table-bordered">
                                <thead><tr><th>Week</th><th>Status</th><th>Action</th></tr></thead>
                                <tbody>`;

                customer.installments.forEach(ins => {
                    const statusClass = ins.paid ? 'table-success' : 'table-danger';
                    const actionBtn = ins.paid
                        ? `<span class="text-success">Paid (${ins.date})</span>`
                        : `<button class="btn btn-sm btn-warning" onclick="showConfirm(${customer.id}, ${ins.week}, '${customer.name}', '${customer.phone}')">Mark Paid</button>`;

                    html += `
                        <tr class="${statusClass}">
                            <td>Week ${ins.week}</td>
                            <td>${ins.paid ? 'Paid' : 'Due'}</td>
                            <td>${actionBtn}</td>
                        </tr>`;
                });

                html += `</tbody></table></div></div>`;
                container.innerHTML += html;
            });
        });
}

function showConfirm(customerId, week, name, phone) {
    selectedCustomerId = customerId;
    selectedWeek = week;
    document.getElementById('confirmText').innerText =
        `Are you sure you want to mark Week ${week} as paid for ${name} (${phone})?`;

    const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
    modal.show();
}

function markInstallmentPaid(customerId, week) {
    fetch(`/mark_paid/${customerId}/${week}`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert('Payment marked successfully');
                fetchResults(document.getElementById('searchBar').value);
            } else {
                alert('Error updating payment');
            }
        });
}
