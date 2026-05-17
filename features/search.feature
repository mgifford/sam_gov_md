@ui @fast @pilot @search
Feature: Search SAM.gov opportunities
  # Traceability:
  # - DEFINITION_OF_DONE.md §5 GitHub Pages dashboard and §7 Search index
  # - FEATURES.md §6 Search page (`docs/search.html`)

  Background:
    Given the docs site is served locally
    And I open the Search page

  @scenario-search-keyword
  Scenario: Search by keyword returns visible opportunities
    When I enter "web" into the search box
    Then matching opportunities are shown in the results list
    And the stats area confirms matching results were found

  @scenario-search-status-open @slow
  Scenario: Filtering by open status narrows results to open opportunities
    When I select "Open Opportunities" in the status filter
    Then only open opportunities are shown in the results list
    And the active filters area shows the selected status filter
