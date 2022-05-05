

document.addEventListener('DOMContentLoaded', function() {
  var elems = document.querySelectorAll('.datepicker');
  var instances = M.Datepicker.init(elems, {});

  elems = document.querySelectorAll('.timepicker');
  instances = M.Timepicker.init(elems, {});

  elems = document.querySelectorAll('select');
  instances = M.FormSelect.init(elems, {});
});
