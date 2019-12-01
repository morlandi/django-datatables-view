'use strict';

window.DatatablesViewUtils = (function() {

    //var _search_icon_html = '<div style="border: 1px solid #ccc; text-align: center;">?</div>';
    var _options = {};

    var _html_daterange_widget =
        'From: <input type="date" id="date_from" class="datepicker">' +
        'To: <input type="date" id="date_to" class="datepicker">';


    function init(options) {
        /*
            Example:

            DatatablesViewUtils.init({
                search_icon_html: '<i class="fa fa-search"></i>',
                language: {
                },
                fn_daterange_widget_initialize: function(table, data) {
                    var wrapper = table.closest('.dataTables_wrapper');
                    var toolbar = wrapper.find(".toolbar");
                    toolbar.html(
                        '<div class="daterange" style="float: left; margin-right: 6px;">' +
                        '{% trans "From" %}: <input type="text" class="date_from" autocomplete="off">' +
                        '&nbsp;&nbsp;' +
                        '{% trans "To" %}: <input type="text" class="date_to" autocomplete="off">' +
                        '</div>'
                    );
                    var date_pickers = toolbar.find('.date_from, .date_to');
                    date_pickers.datepicker();
                    date_pickers.on('change', function(event) {
                        // Annotate table with values retrieved from date widgets
                        var dt_from = toolbar.find('.date_from').data("datepicker");
                        var dt_to = toolbar.find('.date_to').data("datepicker");
                        table.data('date_from', dt_from ? dt_from.getFormattedDate("yyyy-mm-dd") : '');
                        table.data('date_to', dt_to ? dt_to.getFormattedDate("yyyy-mm-dd") : '');
                        // Redraw table
                        table.api().draw();
                    });
                }
            });


            then:

                <div class="table-responsive">
                    <table id="datatable" width="100%" class="table table-striped table-bordered dataTables-log">
                    </table>
                </div>

                <script language="javascript">
                    $(document).ready(function() {

                        // Subscribe "rowCallback" event
                        $('#datatable').on('rowCallback', function(event, table, row, data ) {
                            //$(e.target).show();
                            console.log('rowCallback(): table=%o', table);
                            console.log('rowCallback(): row=%o', row);
                            console.log('rowCallback(): data=%o', data);
                        }

                        // Initialize table
                        DatatablesViewUtils.initialize_table(
                            $('#datatable'),
                            "{% url 'frontend:object-datatable' model|app_label model|model_name %}"
                        );
                    });
                </script>

        */
        _options = options;

        if (!('language' in _options)) {
            _options.language = {};
        }
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

    /*
    function getCookie(cname) {
        var name = cname + "=";
        var ca = document.cookie.split(';');
        for(var i=0; i<ca.length; i++) {
            var c = ca[i];
            while (c.charAt(0)==' ') c = c.substring(1);
            if(c.indexOf(name) == 0)
            return c.substring(name.length,c.length);
        }
        return "";
    }
    */

    function getCookie(name) {
        var value = '; ' + document.cookie,
            parts = value.split('; ' + name + '=');
        if (parts.length == 2) return parts.pop().split(';').shift();
    }

    function _setup_column_filters(table, data) {

        if (data.show_column_filters) {

            var filter_row = '<tr class="datatable-column-filter-row">';
            $.each(data.columns, function(index, item) {
                if (item.visible) {
                    if (item.searchable) {
                        //var placeholder = (_options.language.search === undefined ? 'Search:' : _options.language.search) + ' ' + item.title;
                        var placeholder = '...';
                        filter_row += '<th><input type="text" data-index="' + index.toString() + '" placeholder="' + placeholder + '"></input></th>';
                    }
                    else {
                        if (index == 0) {
                            var search_icon_html = _options.search_icon_html === undefined ?
                                '<div style="border: 1px solid #ccc; text-align: center;">?</div>' : _options.search_icon_html;
                            //filter_row += '<th><i class="fa fa-search"></i>&nbsp;</th>';
                            filter_row += '<th>' + search_icon_html + '</th>';
                        }
                        else {
                            filter_row += '<th></i>&nbsp;</th>';
                        }
                    }
                }
            });
            filter_row += '</tr>';

            var wrapper = table.closest('.dataTables_wrapper');
            $(filter_row).appendTo(
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


    function _daterange_widget_initialize(table, data) {
        if (data.show_date_filters) {
            if (_options.fn_daterange_widget_initialize) {
                _options.fn_daterange_widget_initialize(table, data);
            }
            else {
                var wrapper = table.closest('.dataTables_wrapper');
                var toolbar = wrapper.find(".toolbar");
                toolbar.html(
                    '<div class="daterange" style="float: left; margin-right: 6px;">' +
                    'From: <input type="date" class="date_from datepicker">' +
                    'To: <input type="date" class="date_to datepicker">' +
                    '</div>'
                );
                toolbar.find('.date_from, .date_to').on('change', function(event) {
                    // Annotate table with values retrieved from date widgets
                    table.data('date_from', wrapper.find('.date_from').val());
                    table.data('date_to', wrapper.find('.date_to').val());
                    // Redraw table
                    table.api().draw();
                });
            }
        }
    }


    function after_table_initialization(table, data, url) {
        _bind_row_tools(table, url);
        _setup_column_filters(table, data);
    }


    function _write_footer(table, html) {
        var wrapper = table.closest('.dataTables_wrapper');
        var footer = wrapper.find('.dataTables_extraFooter');
        if (footer.length <= 0) {
            $('<div class="dataTables_extraFooter"></div>').appendTo(wrapper);
            footer = wrapper.find('.dataTables_extraFooter');
        }
        footer.html(html);
    }

    function initialize_table(element, url, extra_options={}, extra_data={}) {

        $.ajax({
            type: 'GET',
            url: url + '?action=initialize',
            dataType: 'json'
        }).done(function(data, textStatus, jqXHR) {

            // https://datatables.net/manual/api#Accessing-the-API
            // It is important to note the difference between:
            //    - $(selector).DataTable(): returns a DataTables API instance
            //    - $(selector).dataTable(): returns a jQuery object
            // An api() method is added to the jQuery object so you can easily access the API,
            // but the jQuery object can be useful for manipulating the table node,
            // as you would with any other jQuery instance (such as using addClass(), etc.).

            var options = {
                processing: true,
                serverSide: true,
                scrollX: true,
                autoWidth: true,
                dom: '<"toolbar">lrftip',
                language: _options.language,
                // language: {
                //     "decimal":        "",
                //     "emptyTable":     "Nessun dato disponibile per la tabella",
                //     "info":           "Visualizzate da _START_ a _END_ di _TOTAL_ entries",
                //     "infoEmpty":      "Visualizzate da 0 a 0 di 0 entries",
                //     "infoFiltered":   "(filtered from _MAX_ total entries)",
                //     "infoPostFix":    "",
                //     "thousands":      ",",
                //     "lengthMenu":     "Visualizza _MENU_ righe per pagina",
                //     "loadingRecords": "Caricamento in corso ...",
                //     "processing":     "Elaborazione in corso ...",
                //     "search":         "Cerca:",
                //     "zeroRecords":    "Nessun record trovato",
                //     "paginate": {
                //         "first":      "Prima",
                //         "last":       "Ultima",
                //         "next":       "Prossima",
                //         "previous":   "Precedente"
                //     },
                //     "aria": {
                //         "sortAscending":  ": activate to sort column ascending",
                //         "sortDescending": ": activate to sort column descending"
                //     }
                // },
                ajax: function(data, callback, settings) {
                      var table = $(this);
                      data.date_from = table.data('date_from');
                      data.date_to = table.data('date_to');
                      if (extra_data) {
                          Object.assign(data, extra_data);
                      }
                      console.log("data tx: %o", data);
                      $.ajax({
                          type: 'POST',
                          url: url,
                          data: data,
                          dataType: 'json',
                          cache: false,
                          crossDomain: false,
                          headers: {'X-CSRFToken': getCookie('csrftoken')}
                      }).done(function(data, textStatus, jqXHR) {
                          console.log('data rx: %o', data);
                          callback(data);

                          var footer_message = data.footer_message;
                          if (footer_message !== null) {
                              _write_footer(table, footer_message);
                          }

                      }).fail(function(jqXHR, textStatus, errorThrown) {
                          console.log('ERROR: ' + jqXHR.responseText);
                      });
                },
                columns: data.columns,
                lengthMenu: data.length_menu,
                order: data.order,
                initComplete: function() {
                    // HACK: wait 200 ms then adjust the column widths
                    // of all visible tables
                    setTimeout(function() {
                        DatatablesViewUtils.adjust_table_columns();
                    }, 200);

                    // Notify subscribers
                    //console.log('Broadcast initComplete()');
                    table.trigger(
                        'initComplete', [table]
                    );
                },
                drawCallback: function(settings) {
                    // Notify subscribers
                    //console.log('Broadcast drawCallback()');
                    table.trigger(
                        'drawCallback', [table, settings]
                    );
                },
                rowCallback: function(row, data) {
                    // Notify subscribers
                    //console.log('Broadcast rowCallback()');
                    table.trigger(
                        'rowCallback', [table, row, data]
                    );
                },
                footerCallback: function (row, data, start, end, display) {
                    // Notify subscribers
                    //console.log('Broadcast footerCallback()');
                    table.trigger(
                        'footerCallback', [table, row, data, start, end, display]
                    );
                }
            }

            if (extra_options) {
                Object.assign(options, extra_options);
            }

            var table = element.dataTable(options);

            _daterange_widget_initialize(table, data);
            after_table_initialization(table, data, url);
        })


        function redraw_all_tables() {
            $.fn.dataTable.tables({
                api: true
            }).draw();
        }


        // Redraw table holding the current paging position
        function redraw_table(element) {
            var table = $(element).closest('table.dataTable');
            // console.log('element: %o', element);
            // console.log('table: %o', table);
            table.DataTable().ajax.reload(null, false);
        }
    }

    return {
        init: init,
        initialize_table: initialize_table,
        after_table_initialization: after_table_initialization,
        adjust_table_columns: adjust_table_columns,
        redraw_all_tables: redraw_all_tables,
        redraw_table: redraw_table
    };

})();
