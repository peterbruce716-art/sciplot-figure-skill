args <- commandArgs(trailingOnly = TRUE)

get_arg <- function(flag, default = NULL) {
  hit <- which(args == flag)
  if (length(hit) == 0 || hit[length(hit)] == length(args)) {
    return(default)
  }
  args[hit[length(hit)] + 1]
}

has_flag <- function(flag) {
  flag %in% args
}

out_dir <- get_arg("--out-dir", "outputs/r_visualspec_render")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

write_manifest <- function(payload) {
  manifest <- file.path(out_dir, "render_manifest.json")
  lines <- c(
    "{",
    sprintf('  "schema": "scientificfigure.r_render_manifest.v1",'),
    sprintf('  "backend": "base_r",'),
    sprintf('  "status": "%s",', payload$status),
    sprintf('  "png": "%s",', normalizePath(payload$png, winslash = "/", mustWork = FALSE)),
    sprintf('  "pdf": "%s",', normalizePath(payload$pdf, winslash = "/", mustWork = FALSE)),
    sprintf('  "svg": "%s"', normalizePath(payload$svg, winslash = "/", mustWork = FALSE)),
    "}"
  )
  writeLines(lines, manifest, useBytes = TRUE)
  manifest
}

render_demo <- function() {
  x <- seq(0, 10, length.out = 200)
  y <- sin(x) * exp(-x / 12)
  png_path <- file.path(out_dir, "render.png")
  pdf_path <- file.path(out_dir, "render.pdf")
  svg_path <- file.path(out_dir, "render.svg")

  draw <- function() {
    par(family = "serif", mar = c(4, 4, 1, 1), las = 1)
    plot(x, y, type = "l", lwd = 2, col = "#1b35ff", xlab = "x", ylab = "response")
    points(x[seq(1, length(x), by = 25)], y[seq(1, length(y), by = 25)], pch = 16, cex = 0.6)
    grid(col = "#dddddd")
  }

  png(png_path, width = 900, height = 600, res = 120)
  draw()
  dev.off()
  pdf(pdf_path, width = 7.5, height = 5)
  draw()
  dev.off()
  svg(svg_path, width = 7.5, height = 5)
  draw()
  dev.off()
  write_manifest(list(status = "pass", png = png_path, pdf = pdf_path, svg = svg_path))
}

render_spec <- function(spec_path) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("jsonlite is required for --spec mode; use --demo or install jsonlite.")
  }
  spec <- jsonlite::fromJSON(spec_path, simplifyVector = FALSE)
  panel <- spec$panels[[1]]
  plot <- panel$plots[[1]]
  data <- plot$data
  x <- unlist(data$x)
  y <- unlist(data$y)
  png_path <- file.path(out_dir, "render.png")
  pdf_path <- file.path(out_dir, "render.pdf")
  svg_path <- file.path(out_dir, "render.svg")

  draw <- function() {
    par(family = "serif", mar = c(4, 4, 1, 1), las = 1)
    plot(x, y, type = "l", lwd = 2, col = "#1b35ff",
         xlab = panel$axes$x$label, ylab = panel$axes$y$label)
    grid(col = "#dddddd")
  }

  png(png_path, width = 900, height = 600, res = 120)
  draw()
  dev.off()
  pdf(pdf_path, width = 7.5, height = 5)
  draw()
  dev.off()
  svg(svg_path, width = 7.5, height = 5)
  draw()
  dev.off()
  write_manifest(list(status = "pass", png = png_path, pdf = pdf_path, svg = svg_path))
}

if (has_flag("--help")) {
  cat("Usage: Rscript render_visualspec_r.R --demo --out-dir outputs/r_demo\n")
  cat("   or: Rscript render_visualspec_r.R --spec visualspec.json --out-dir outputs/r_render\n")
  quit(status = 0)
}

if (has_flag("--demo")) {
  cat(render_demo(), "\n")
} else {
  spec_path <- get_arg("--spec")
  if (is.null(spec_path)) {
    stop("Provide --demo or --spec visualspec.json")
  }
  cat(render_spec(spec_path), "\n")
}
