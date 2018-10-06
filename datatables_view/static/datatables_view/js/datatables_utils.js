

function datatables_bind_row_tools(table, url, custom_id='id')
{
    table.on('click', 'td.dataTables_row-tools .plus, td.dataTables_row-tools .minus', function(event) {
        event.preventDefault();
        var tr = $(this).closest('tr');
        var row = table.row(tr);
        if (row.child.isShown()) {
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            row.child(datatables_load_row_details(row.data(), url), 'details').show('slow');
            tr.addClass('shown');
        }
    });
}

function datatables_load_row_details(rowData, url, custom_id) {
    var div = $('<div/>')
        .addClass('loading')
        .text('Loading...');

    $.ajax({
        url: url,
        data: {
            action: 'details',
            id: rowData[custom_id]
        },
        dataType: 'json',
        success: function(json) {
            div.html(json.html).removeClass('loading');
        }
    });

    return div;
}

function datatables_adjust_table_columns() {
    // Adjust the column widths of all visible tables
    // https://datatables.net/reference/api/%24.fn.dataTable.tables()
    $.fn.dataTable
        .tables({
            visible: true,
            api: true
        })
        .columns.adjust();
}

