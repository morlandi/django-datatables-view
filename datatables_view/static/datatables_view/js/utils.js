'use strict';

window.DatatablesViewUtils = (function() {

    var _search_icon_html = '<div style="border: 1px solid #ccc; text-align: center;">?</div>';

    function init(search_icon_html) {
        _search_icon_html = search_icon_html;
    }

    function _handle_column_filter(table, data, target) {
        var index = target.data('index');
        var value = target.val();

        var column = table.api().column(index);
        if (value != column.search()) {
            console.log('index: %o', index);
            console.log('value: %o', value);
            console.log('column: %o (%o)', column, column.length);
            column.search(value).draw();
        }
    };


    function _setup_column_filters(table, data) {

        if (data.show_column_filters) {

            var footer = '<tr class="datatable-column-filter-row">';
            $.each(data.columns, function(index, item) {
                if (item.visible) {
                    if (item.searchable) {
                        var placeholder = 'Search ' + item.title;
                        footer += '<th><input type="text" data-index="' + index.toString() + '" placeholder="' + placeholder + '"></input></th>';
                    }
                    else {
                        if (index == 0) {
                            //footer += '<th><i class="fa fa-search"></i>&nbsp;</th>';
                            footer += '<th>' + _search_icon_html + '</th>';
                        }
                        else {
                            footer += '<th></i>&nbsp;</th>';
                        }
                    }
                }
            });
            footer += '</tr>';

            var wrapper = table.closest('.dataTables_wrapper');
            $(footer).appendTo(
                wrapper.find('thead')
            );

            var column_filter_row = wrapper.find('.datatable-column-filter-row')
            column_filter_row.find('input').off().on('keyup change', function(event) {
                var target = $(event.target);
                _handle_column_filter(table, data, target);
            });

        }
    };


    function _bind_row_tools(table, url, custom_id='id')
    {
        table.api().on('click', 'td.dataTables_row-tools .plus, td.dataTables_row-tools .minus', function(event) {
            event.preventDefault();
            var tr = $(this).closest('tr');
            var row = table.api().row(tr);
            if (row.child.isShown()) {
                row.child.hide();
                tr.removeClass('shown');
            }
            else {
                row.child(_load_row_details(row.data(), url, custom_id), 'details').show('slow');
                tr.addClass('shown');
            }
        });
    };


    function _load_row_details(rowData, url, custom_id) {
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
    };


    function adjust_table_columns() {
        // Adjust the column widths of all visible tables
        // https://datatables.net/reference/api/%24.fn.dataTable.tables()
        $.fn.dataTable
            .tables({
                visible: true,
                api: true
            })
            .columns.adjust();
    };


    function after_initialization(table, data, url) {
        _bind_row_tools(table, url);
        _setup_column_filters(table, data);
    }


    return {
        init: init,
        after_initialization: after_initialization,
        adjust_table_columns: adjust_table_columns
    };

})();
