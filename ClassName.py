import os
import os.path
import re

import sublime
import sublime_plugin


class ClassNameCommand(sublime_plugin.WindowCommand):
	def getFilePath(self, paths=None):
		if paths:
			file = '*'.join(paths)
		else:
			view = sublime.active_window().active_view()
			file = view.file_name() if view else None
		return file


class ClassnameCopyCommand(ClassNameCommand):
	def run(self, paths=None, event=None):
		file = self.getFilePath(paths)
		view = sublime.active_window().active_view()
		point = None
		if event and isinstance(event, dict):
			point = event.get('text_point')
		fullname = self.getClassName(file, view, point) if file else None
		if fullname:
			settings = sublime.load_settings('ClassName.sublime-settings')
			prefix = settings.get('classname_prefix')
			suffix = settings.get('classname_suffix')
			prefix = prefix if prefix else ''
			suffix = suffix if suffix else ''
			fullname = prefix + fullname + suffix
			sublime.set_clipboard(fullname)
			sublime.status_message("Copied class full name: " + fullname)
		else:
			sublime.status_message("Can not find class name")

	def getClassName(self, file, view=None, point=None):
		if not file:
			return None

		moduleName = self.getModuleName(file)
		if not moduleName:
			return None

		symbolName = self.getCurrentPythonSymbolName(file, view, point)
		if not symbolName and point is not None:
			symbolName = self.getCurrentPythonSymbolName(file, view, None)
		if not symbolName:
			symbolName = self.getNearestPythonClassName(view, point)
		if not symbolName:
			symbolName = self.getNearestPythonFunctionName(view, point)
		if not symbolName:
			return moduleName

		separator = sublime.load_settings('ClassName.sublime-settings').get('namespace_separator')
		return moduleName + separator + symbolName

	def getModuleName(self, file):
		folders = sublime.active_window().folders()
		(path, ext) = os.path.splitext(file)
		extLen = len(ext)
		for dir in folders:
			if 0 == file.find(dir):
				fullname = file[len(dir) + 1:]
				if extLen > 0:
					fullname = fullname[0:-extLen]
				fullname = fullname.replace(
					os.sep,
					sublime.load_settings('ClassName.sublime-settings').get('namespace_separator')
				)
				return fullname

		return None

	def getCurrentPythonSymbolName(self, file, view, point=None):
		if not view or not file.endswith('.py'):
			return None
		viewFile = view.file_name()
		if not viewFile:
			return None
		# Side-bar context menu can provide a path variant (e.g. symlink/case);
		# compare normalized real paths to keep class detection working.
		if os.path.realpath(viewFile) != os.path.realpath(file):
			return None
		if point is None:
			if not view.sel():
				return None
			point = view.sel()[0].begin()
		row, _ = view.rowcol(point)
		line = row + 1
		source = view.substr(sublime.Region(0, view.size()))
		lines = source.splitlines()
		current_index = max(0, min(line - 1, len(lines) - 1))

		# AST in ST plugin runtime is too old for robust end-position checks.
		# Use indentation-based scan to detect current class/function context.
		class_name = None
		class_indent = None
		function_name = None
		function_indent = None

		for idx in range(0, current_index + 1):
			text = lines[idx]
			stripped = text.strip()
			if not stripped or stripped.startswith('#'):
				continue

			indent = len(text) - len(text.lstrip(' \t'))
			class_match = re.match(r'^\s*class\s+([A-Za-z_]\w*)\b', text)
			func_match = re.match(r'^\s*(?:async\s+def|def)\s+([A-Za-z_]\w*)\b', text)

			if class_match:
				while class_indent is not None and indent <= class_indent:
					class_name = None
					class_indent = None
					function_name = None
					function_indent = None
				class_name = class_match.group(1)
				class_indent = indent
				function_name = None
				function_indent = None
				continue

			if func_match:
				while function_indent is not None and indent <= function_indent:
					function_name = None
					function_indent = None
				if class_indent is not None and indent <= class_indent:
					class_name = None
					class_indent = None
				function_name = func_match.group(1)
				function_indent = indent
				continue

			if class_indent is not None and indent <= class_indent:
				class_name = None
				class_indent = None
				function_name = None
				function_indent = None
			elif function_indent is not None and indent <= function_indent:
				function_name = None
				function_indent = None

		if class_name and function_name:
			return class_name + '.' + function_name
		if function_name:
			return function_name
		if class_name:
			return class_name
		return None

	def getNearestPythonClassName(self, view, point=None):
		if not view:
			return None

		source = view.substr(sublime.Region(0, view.size()))
		classLines = []
		for idx, lineText in enumerate(source.splitlines()):
			matched = re.match(r'^\s*class\s+([A-Za-z_]\w*)\b', lineText)
			if matched:
				classLines.append((idx + 1, matched.group(1)))

		if not classLines:
			return None

		if point is None:
			if not view.sel():
				return classLines[0][1]
			point = view.sel()[0].begin()

		row, _ = view.rowcol(point)
		line = row + 1

		for classLine, className in classLines:
			if classLine >= line:
				return className

		return classLines[-1][1]

	def getNearestPythonFunctionName(self, view, point=None):
		if not view:
			return None

		source = view.substr(sublime.Region(0, view.size()))
		functionLines = []
		for idx, lineText in enumerate(source.splitlines()):
			matched = re.match(r'^\s*(?:async\s+def|def)\s+([A-Za-z_]\w*)\b', lineText)
			if matched:
				functionLines.append((idx + 1, matched.group(1)))

		if not functionLines:
			return None

		if point is None:
			if not view.sel():
				return functionLines[0][1]
			point = view.sel()[0].begin()

		row, _ = view.rowcol(point)
		line = row + 1

		for funcLine, funcName in functionLines:
			if funcLine >= line:
				return funcName

		return functionLines[-1][1]

	def is_visible(self, paths=None):
		file = self.getFilePath(paths)
		return os.path.isfile(file) if file else False


class ClassnameCopyPackageCommand(ClassNameCommand):
	def run(self, paths=None):
		file = self.getFilePath(paths)
		package = self.getPackage(file) if file else None
		if package:
			sublime.set_clipboard(package)
			sublime.status_message("Copied class package path: " + package)
		else:
			sublime.status_message("Can not find package")

	def getPackage(self, file):
		file = file if os.path.isdir(file) else os.path.dirname(file)
		folders = sublime.active_window().folders()
		for dir in folders:
			if 0 == file.find(dir):
				package = file[len(dir) + 1:]
				package = package.replace(
					os.sep,
					sublime.load_settings('ClassName.sublime-settings').get('namespace_separator')
				)
				return package

		return None
